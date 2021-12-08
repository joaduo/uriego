# userver.py Demo of simple uasyncio-based echo server
import usocket as socket
import uasyncio as asyncio
import riego
import logging
import ujson


def web_page():
    html = """<html>

<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>

<body>
    <h2>ESP MicroPython Web Server</h2>

    <p>
        <i class="fas fa-lightbulb fa-3x" style="color:#c81919;"></i>
        <a href=\"?led_2_on\"><button class="button">LED ON</button></a>
    </p>
    <p>
        <i class="far fa-lightbulb fa-3x" style="color:#000000;"></i>
        <a href=\"?led_2_off\"><button class="button button1">LED OFF</button></a>
    </p>

</body>

</html>"""
    return html


class Server:
    def __init__(self, host='0.0.0.0', port=80, backlog=5, timeout=20):
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
            try:
                request = await asyncio.wait_for(sreader.readline(), self.timeout)
                request_trailer = await asyncio.wait_for(sreader.read(-1), self.timeout)
                logging.info('request={request!r}, cid={cid}', request=request, cid=cid)
            except asyncio.TimeoutError:
                request = b''
            if request == b'':
                raise OSError
            verb, path = request.split()[0:2]
            logging.info(path)
            if path == b'/favicon.ico':
                status = 404
                msg = 'NOT FOUND'
                content = ''
            elif path == b'/task_list':
                if verb == b'POST':
                    payload = request_trailer[request_trailer.rfind(b'\r\n\r\n')+4:].decode('utf8')
                    riego.task_list.load_tasks(ujson.loads(payload))
                status = 200
                msg = 'OK'
                content = str(riego.task_list.table_json)
            else:
                status = 200
                msg = 'OK'
                content = web_page()
            header = ('HTTP/1.1 %s %s\n' % (status, msg) +
                      'Content-Type: text/html\n'
                      'Connection: close\n\n')
            swriter.write(header + content)
            await swriter.drain()
        except OSError:
            pass
        logging.info('Client {cid} disconnect.', cid=cid)
        swriter.close()
        await swriter.wait_closed()
        logging.info('Client {cid} socket closed.', cid=cid)

    async def close(self):
        logging.info('Closing server')
        self.server.close()
        await self.server.wait_closed()
        logging.info('Server closed.')


def main():
    server = Server()
    try:
        asyncio.run(server.run())
        asyncio.run(riego.loop_tasks())
    finally:
        asyncio.run(server.close())
        _ = asyncio.new_event_loop()

main()


