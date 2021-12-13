import uasyncio
import ujson
import machine
import utime
import riego
import log
import webserver


def serve_request(verb, path, request_trailer):
    global AUTH_TOKEN
    log.info(path)
    content_type = 'application/json'
    status = 200
    if path == b'/task_list':
        if verb == webserver.POST:
            riego.task_list.load_tasks(webserver.extract_json(request_trailer))
        payload = ujson.dumps(riego.task_list.table_json)
    elif path == b'/manual_task':
        if verb == webserver.POST:
            tasks = webserver.extract_json(request_trailer)
            riego.manual_names.clear()
            riego.manual_names += tasks
        payload = ujson.dumps(riego.manual_names)
    elif path == b'/time':
        if verb == webserver.POST:
            t = webserver.extract_json(request_trailer)
            log.info('set time to {t}', t=t)
            #Convert `time.localtime()` output
            # to `machine.RTC.datetime()` args
            machine.RTC().datetime((t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0))
        payload = ujson.dumps(utime.localtime())
    elif path == b'/auth_token':
        if verb == webserver.POST:
            payload = webserver.extract_json(request_trailer)
            log.info('setting new token')
            AUTH_TOKEN=payload
            payload = ujson.dumps(dict(payload='token rotated'))
        else:
            content_type = 'text/html'
            payload = webserver.web_page('POST {"auth_token":"<secret>", "payload":"<new secret>"}')
    else:
        status = 404
        content_type = 'text/html'
        payload = webserver.web_page('404 Not found')
    return webserver.response(status, content_type, payload)


def main():
    gmt, localt = utime.gmtime(), utime.localtime()
    assert gmt == localt
    riego.init_devices()
    server = webserver.Server(serve_request)
    log.garbage_collect()
    try:
        uasyncio.run(server.run())
        uasyncio.run(riego.loop_tasks())
    finally:
        uasyncio.run(server.close())
        _ = uasyncio.new_event_loop()


if __name__ == '__main__':
    main()

