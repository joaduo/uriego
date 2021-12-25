import uasyncio
import ujson
import machine
import utime
import riego
import log
import webserver
import devices


LIGHT_PIN=2
light = devices.InvertedPin(LIGHT_PIN, machine.Pin.OUT)


async def blink():
    light.off()
    await uasyncio.sleep(0.2)
    light.on()


async def serve_request(verb, path, request_trailer):
    log.info(path)
    uasyncio.create_task(blink())
    content_type = 'application/json'
    status = 200
    if path == b'/tasks':
        if verb == webserver.POST:
            riego.task_list.load_tasks(webserver.extract_json(request_trailer))
        payload = ujson.dumps(riego.task_list.table_json)
    elif path == b'/stop':
        if verb == webserver.POST:
            payload = webserver.extract_json(request_trailer)
            # Stop anything to be ran
            riego.task_list.manual_queue.clear()
            if payload.get('stop_all'):
                await riego.task_list.stop(all_=True)
            else:
                await riego.task_list.stop(names=payload['names'])
            payload = ujson.dumps(dict(payload='stopped'))
        else:
            content_type = 'text/html'
            payload = webserver.web_page('POST "payload":{"stop_all":true/false, "names":["test"]}')
    elif path == b'/manual':
        if verb == webserver.POST:
            tasks = webserver.extract_json(request_trailer)
            #riego.task_list.manual_names.clear()
            riego.task_list.manual_queue.update(tasks)
        payload = ujson.dumps(riego.task_list.manual_queue)
    elif path == b'/running':
        payload = ujson.dumps({t.name:t.remaining
                               for t in riego.task_list.table if t.running})
    elif path == b'/time':
        if verb == webserver.POST:
            t = webserver.extract_json(request_trailer)
            log.info('set time to {t}', t=t)
            #Convert `time.localtime()` output
            # to `machine.RTC.datetime()` args
            machine.RTC().datetime((t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0))
        payload = ujson.dumps(utime.localtime())
    elif path == b'/auth':
        if verb == webserver.POST:
            payload = webserver.extract_json(request_trailer)
            log.info('setting new token')
            webserver.AUTH_TOKEN=payload
            payload = ujson.dumps(dict(payload='token rotated'))
        else:
            content_type = 'text/html'
            payload = webserver.web_page('POST {"auth_token":"<secret>", "payload":"<new secret>"}')
    else:
        content_type = 'text/html'
        if path == b'/':
            resp = webserver.response(status, content_type, '')
            return resp, webserver.serve_file('/static/client.html')
        else:
            status = 404
            payload = webserver.web_page('404 Not found')
    return webserver.response(status, content_type, payload)


def main():
    gmt, localt = utime.gmtime(), utime.localtime()
    assert gmt == localt
    riego.init_devices()
    server = webserver.Server(serve_request)
    server.static_path = b'/static/'
    riego.task_list.load_tasks([{"from_day": [1, 1], "week_days": [], "name": "abajo",  "end": [0, 20, 0],
                                 "gate": 1, "start": [0, 0, 0], "to_day": [1, 2], "pump": 0},
                                {"from_day": [1, 1], "week_days": [], "name": "arriba", "end": [0, 10, 0],
                                 "gate": 0, "start": [0, 0, 0], "to_day": [1, 2], "pump": 0}])
    log.garbage_collect()
    try:
        light.on()
        uasyncio.run(server.run())
        uasyncio.run(riego.loop_tasks())
    finally:
        uasyncio.run(server.close())
        _ = uasyncio.new_event_loop()


if __name__ == '__main__':
    main()

