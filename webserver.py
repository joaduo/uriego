import uasyncio
import log
import ujson
import utime
import sys


AUTH_TOKEN='1234'
CONN_TIMEOUT=10
STATUS_CODES = {
    200:'OK',
    404:'NOT FOUND',
    403:'FORBIDDEN',
    401:'UNAUTHORIZED',
    500:'SERVER ERROR'}
POST = b'POST'
GET = b'GET'


def web_page(msg):
    return "<html><body><p>{}</p></body></html>".format(msg)


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


def serve_file(path):
    with open(path) as fp:
        for line in fp:
            yield line


class Server:
    static_path = b'/static/'
    def __init__(self, serve_request, host='0.0.0.0', port=80, backlog=5, timeout=CONN_TIMEOUT):
        self.serve_request = serve_request
        self.host = host
        self.port = port
        self.backlog = backlog
        self.timeout = timeout
    async def run(self):
        log.info('Opening address={host} port={port}.', host=self.host, port=self.port)
        self.conn_id = 0 #connections ids
        self.server = await uasyncio.start_server(self.accept_conn, self.host, self.port, self.backlog)
    async def accept_conn(self, sreader, swriter):
        self.conn_id += 1
        conn_id = self.conn_id
        log.info('Accepting conn_id={conn_id}', conn_id=conn_id)
        log.garbage_collect()
        try:
            request = await uasyncio.wait_for(sreader.readline(), self.timeout)
            request_trailer = await uasyncio.wait_for(sreader.read(-1), self.timeout)
            log.debug('request={request!r}, conn_id={conn_id}', request=request, conn_id=conn_id)
            verb, path = request.split()[0:2]
            resp_generator = None
            try:
                if path.startswith(self.static_path) and verb == GET:
                    resp = self.serve_static(path)
                else:
                    resp = await self.serve_request(verb, path, request_trailer)
                if isinstance(resp, tuple):
                    resp, resp_generator = resp
            except UnauthorizedError as e:
                resp = response(401, 'text/html', web_page('{} {!r}'.format(e,e)))
            swriter.write(resp)
            if resp_generator:
                for l in resp_generator:
                    swriter.write(l)
        except Exception as e:
            msg = 'Exception e={e} e={e!r} conn_id={conn_id}'.format(e=e, conn_id=conn_id)
            log.debug(msg)
            sys.print_exception(e)
            swriter.write(response(500, 'text/html', web_page(msg)))
        finally:
            await swriter.drain()
            log.debug('Disconnect conn_id={conn_id}.', conn_id=conn_id)
            swriter.close()
            await swriter.wait_closed()
            log.debug('Socket closed conn_id={conn_id}.', conn_id=conn_id)
    async def close(self):
        log.debug('Closing server.')
        self.server.close()
        await self.server.wait_closed()
        log.info('Server closed.')
    def serve_static(self, path):
        if self.file_exists(path):
            resp = response(200, 'text/html', '')
            return resp, serve_file(path)
        return response(404, 'text/html', web_page('404 Not Found'))
    def file_exists(self, path):
        try:
            with open(path):
                pass
            return True
        except:
            return False


def main():
    async def serve_request(verb, path, request_trailer):
        log.info('Serving {v} {p}', v=verb, p=path)
        status = 200
        content_type = 'text/html'
        payload = web_page('<h2>Trailer</h2><pre>{}</pre>'.format(request_trailer.decode('utf8')))
        return response(status, content_type, payload)
    server = Server(serve_request)
    log.garbage_collect()
    try:
        uasyncio.run(server.run())
        uasyncio.get_event_loop().run_forever()
    finally:
        uasyncio.run(server.close())
        _ = uasyncio.new_event_loop()


if __name__ == '__main__':
    main()

