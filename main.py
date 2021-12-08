# userver.py Demo of simple uasyncio-based echo server
import usocket as socket
import uasyncio as asyncio
import riego
import logging
import ujson
import machine


def web_page(msg):
    html = """<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
    <h2>MicroRiego Web Server</h2>
    <p>
        {msg}
    </p>
</body>
</html>"""
    return html.format(msg=msg)


class Server:
    def __init__(self, host='0.0.0.0', port=80, backlog=5, timeout=5):
        self.host = host
        self.port = port
        self.backlog = backlog
        self.timeout = timeout
    async def run(self):
        logging.info('Awaiting client connection.')
        self.cid = 0
        self.server = await asyncio.start_server(self.run_client, self.host, self.port, self.backlog)
    async def run_client(self, sreader, swriter):
        self.cid += 1
        cid = self.cid
        logging.info('Got connection from client cid={cid}', cid=cid)
        try:
            request = await asyncio.wait_for(sreader.readline(), self.timeout)
            request_trailer = await asyncio.wait_for(sreader.read(-1), self.timeout)
            logging.info('request={request!r}, cid={cid}', request=request, cid=cid)
            verb, path = request.split()[0:2]
            try:
                resp = serve_request(verb, path, request_trailer)
            except Exception as e:
                resp = response(500, 'text/html', web_page('Exception: %s %r' % (e,e)))
            swriter.write(resp)
            await swriter.drain()
        except Exception as e:
            logging.info('Exception e={e}', e=e)
            #raise
        logging.info('Client {cid} disconnect.', cid=cid)
        swriter.close()
        await swriter.wait_closed()
        logging.info('Client {cid} socket closed.', cid=cid)
        riego.garbage_collect()

    async def close(self):
        logging.info('Closing server')
        self.server.close()
        await self.server.wait_closed()
        logging.info('Server closed.')


def response(status, content_type, payload):
    status_msg = {200:'OK',
                  404:'NOT FOUND',
                  500:'SERVER ERROR'}[status]
    header = ('HTTP/1.1 %s %s\n' % (status, status_msg) +
          'Content-Type: %s\n' % content_type +
          'Connection: close\n\n')
    return header + payload


def extract_json(request):
    payload = request[request.rfind(b'\r\n\r\n')+4:].decode('utf8')
    return ujson.loads(payload)


def serve_request(verb, path, request_trailer):
    logging.info(path)
    content_type = 'application/json'
    status = 200
    if path == b'/task_list':
        if verb == b'POST':
            riego.task_list.load_tasks(extract_json(request_trailer))
        payload = ujson.dumps(riego.task_list.table_json)
    elif path == b'/time':
        if verb == b'POST':
            payload = extract_json(request_trailer)
            logging.info('set time to {payload}', payload=payload)
            machine.RTC().datetime(payload)
        payload = ujson.dumps(riego.gmtime())
    else:
        status = 404
        content_type = 'text/html'
        payload = web_page('404 Not found')
    return response(status, content_type, payload)


def main():
    server = Server()
    try:
        asyncio.run(server.run())
        asyncio.run(riego.loop_tasks())
    finally:
        asyncio.run(server.close())
        _ = asyncio.new_event_loop()

main()

