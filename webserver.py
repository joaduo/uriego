import uasyncio
import log
import ujson
import utime
import sys


AUTH_TOKEN='1234'
STATUS_CODES = {
    200:'OK',
    404:'NOT FOUND',
    403:'FORBIDDEN',
    401:'UNAUTHORIZED',
    500:'SERVER ERROR'}
POST = b'POST'

def web_page(msg):
    return "<html><body><p>{}</p></body></html>".format(msg)


class Server:
    def __init__(self, serve_request, host='0.0.0.0', port=80, backlog=5, timeout=20):
        self.serve_request = serve_request
        self.host = host
        self.port = port
        self.backlog = backlog
        self.timeout = timeout
    async def run(self):
        log.info('Opening address={host} port={port}.', host=self.host, port=self.port)
        self.cid = 0 #connections ids
        self.server = await uasyncio.start_server(self.run_client, self.host, self.port, self.backlog)
    async def run_client(self, sreader, swriter):
        self.cid += 1
        cid = self.cid
        log.info('Connection cid={cid}', cid=cid)
        log.garbage_collect()
        try:
            request = await uasyncio.wait_for(sreader.readline(), self.timeout)
            request_trailer = await uasyncio.wait_for(sreader.read(-1), self.timeout)
            log.info('request={request!r}, cid={cid}', request=request, cid=cid)
            verb, path = request.split()[0:2]
            try:
                resp = await self.serve_request(verb, path, request_trailer)
            except UnauthorizedError as e:
                resp = response(401, 'text/html', web_page('{} {!r}'.format(e,e)))
            except Exception as e:
                sys.print_exception(e)
                resp = response(500, 'text/html', web_page('Exception: {} {!r}'.format(e,e)))
            swriter.write(resp)
            await swriter.drain()
        except Exception as e:
            log.info('Exception e={e}', e=e)
            sys.print_exception(e)
            swriter.write('exc={e}'.format(e=e))
            await swriter.drain()
        log.info('Connection {cid} disconnect.', cid=cid)
        swriter.close()
        await swriter.wait_closed()
        log.info('Connection {cid} socket closed.', cid=cid)
    async def close(self):
        log.info('Closing server')
        self.server.close()
        await self.server.wait_closed()
        log.info('Server closed.')


def response(status, content_type, payload):
    resp = 'HTTP/1.1 {} {}\nContent-Type: {}\nConnection: close\n\n{}'.format(
            status, STATUS_CODES[status], content_type, payload)
    return resp


class UnauthorizedError(Exception):
    pass


def extract_json(request):
    log.garbage_collect()
    msg = ujson.loads(request[request.rfind(b'\r\n\r\n')+4:])
    if msg.get('auth_token') != AUTH_TOKEN:
        raise UnauthorizedError('Unauthorized. Send {"auth_token":"<secret>", "payload": ...}')
    return msg['payload']

