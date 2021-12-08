import uasyncio
import riego
import log
import ujson
import machine
import utime


def web_page(msg):
    html = """<html>
<head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body><h2>MicroRiego Web Server</h2><p>{msg}</p></body>
</html>"""
    return html.format(msg=msg)


class Server:
    def __init__(self, host='0.0.0.0', port=80, backlog=5, timeout=20):
        self.host = host
        self.port = port
        self.backlog = backlog
        self.timeout = timeout
    async def run(self):
        log.info('Awaiting client connection.')
        self.cid = 0
        self.server = await uasyncio.start_server(self.run_client, self.host, self.port, self.backlog)
    async def run_client(self, sreader, swriter):
        self.cid += 1
        cid = self.cid
        log.info('Got connection from client cid={cid}', cid=cid)
        riego.garbage_collect()
        try:
            request = await uasyncio.wait_for(sreader.readline(), self.timeout)
            request_trailer = await uasyncio.wait_for(sreader.read(-1), self.timeout)
            log.info('request={request!r}, cid={cid}', request=request, cid=cid)
            verb, path = request.split()[0:2]
            try:
                resp = serve_request(verb, path, request_trailer)
            except UnauthenticatedError as e:
                resp = response(401, 'text/html', web_page('%s %r' % (e,e)))
            except Exception as e:
                resp = response(500, 'text/html', web_page('Exception: %s %r' % (e,e)))
            swriter.write(resp)
            await swriter.drain()
        except uasyncio.TimeoutError:
            swriter.write('Timeout')
            await swriter.drain()
        except Exception as e:
            log.info('Exception e={e}', e=e)
            swriter.write('exc={e}'.format(e=e))
            await swriter.drain()
        log.info('Client {cid} disconnect.', cid=cid)
        swriter.close()
        await swriter.wait_closed()
        log.info('Client {cid} socket closed.', cid=cid)

    async def close(self):
        log.info('Closing server')
        self.server.close()
        await self.server.wait_closed()
        log.info('Server closed.')


def response(status, content_type, payload):
    status_msg = {200:'OK',
                  404:'NOT FOUND',
                  403:'FORBIDDEN',
                  401:'UNAUTHENTICATED',
                  500:'SERVER ERROR'}[status]
    header = ('HTTP/1.1 %s %s\n' % (status, status_msg) +
          'Content-Type: %s\n' % content_type +
          'Connection: close\n\n')
    return header + payload


class UnauthenticatedError(Exception):
    pass


AUTH_TOKEN='1234'
def extract_json(request):
    riego.garbage_collect()
    msg = ujson.loads(request[request.rfind(b'\r\n\r\n')+4:])
    if msg.get('auth_token') != AUTH_TOKEN:
        raise UnauthenticatedError('Unauthorized. Send {"auth_token":"<secret>", "payload": ...}')
    return msg['payload']


POST = b'POST'
def serve_request(verb, path, request_trailer):
    log.info(path)
    content_type = 'application/json'
    status = 200
    if path == b'/task_list':
        if verb == POST:
            riego.task_list.load_tasks(extract_json(request_trailer))
        payload = ujson.dumps(riego.task_list.table_json)
    elif path == b'/time':
        if verb == POST:
            payload = extract_json(request_trailer)
            log.info('set time to {payload}', payload=payload)
            machine.RTC().datetime(payload)
        payload = ujson.dumps(utime.gmtime())
    else:
        status = 404
        content_type = 'text/html'
        payload = web_page('404 Not found')
    return response(status, content_type, payload)


def main():
    server = Server()
    try:
        uasyncio.run(server.run())
        uasyncio.run(riego.loop_tasks())
    finally:
        uasyncio.run(server.close())
        _ = uasyncio.new_event_loop()

main()

