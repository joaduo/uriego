import uasyncio
import ujson
import machine
import utime
import network
import riego
import log
import webserver
import config
config.load()

LIGHT_PIN=2
light = machine.Pin(LIGHT_PIN, machine.Pin.OUT)


async def blink():
    light.off()
    await uasyncio.sleep(0.2)
    light.on()

wifi_tracker = riego.WifiTracker()
task_list = riego.TaskList(wifi_tracker)
app = webserver.Server(static_path='/static/',
                       auth_token=config.get('AUTH_TOKEN'),
                       pre_request_hook=lambda: uasyncio.create_task(blink()))

@app.json()
def wifimode(verb, cfg):
    v = wifi_tracker.is_ap
    if verb == webserver.POST:
        if cfg['is_ap'] != v:
            wifi_tracker.schedule_switch = True
            v = not v
    return dict(is_ap=v)

@app.json()
def wificfg(verb, cfg, auth_token=''):
    if verb == webserver.POST:
        wifi_tracker.json_set(cfg)
        if cfg['reboot']:
            wifi_tracker.schedule_switch = True
    elif auth_token != config.get('AUTH_TOKEN'):
        raise webserver.UnauthorizedError('Please provide a valid auth_token parameter')
    out_cfg = wifi_tracker.json_get(shadow_passwords=True)
    out_cfg['reboot'] = False
    return out_cfg

@app.json()
def tasklistcfg(verb, cfg, auth_token=''):
    if verb == webserver.POST:
        task_list.json_set(cfg)
        if cfg['dump']:
            task_list.dump_cfg()
    elif auth_token != config.get('AUTH_TOKEN'):
        raise webserver.UnauthorizedError('Please provide a valid auth_token parameter')
    out_cfg = task_list.json_get()
    out_cfg['dump'] = False
    return out_cfg

@app.json()
def tasks(verb, payload):
    if verb == webserver.POST:
        task_list.load_tasks(payload)
    return ujson.dumps(task_list.table_json)

@app.json(is_async=True)
async def stop(verb, payload):
    if verb == webserver.POST:
        if payload.get('stop_all'):
            await task_list.stop(all_=True)
        else:
            await task_list.stop(names=payload['names'])
        return 'stopped'
    else:
        return dict(help='POST "payload":{"stop_all":true/false, "names":["test"]}')

@app.json()
def manual(verb, tasks):
    if verb == webserver.POST:
        while tasks:
            task_list.manual_queue.insert(0, tasks.pop())
    return task_list.manual_queue

@app.json()
def running(v, p):
    return {t.name:t.remaining
            for t in task_list.table if t.running}

@app.json()
def time(verb, t):
    if verb == webserver.POST:
        log.info('set time to {t}', t=t)
        #Convert `time.localtime()` output
        # to `machine.RTC.datetime()` args
        machine.RTC().datetime((t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0))
    return utime.localtime()

@app.json()
def auth(verb, password):
    if verb == webserver.POST:
        log.info('setting new token')
        app.auth_token=password
        return dict(payload='token rotated')
    else:
        return dict(help='POST {"auth_token":"<secret>", "payload":"<new secret>"}')

@app.html('/')
def index(verb, _):
    return webserver.serve_file('/client.html', {'@=AUTH_TOKEN=@':config.get('AUTH_TOKEN'),
                                                 '@=SERVER_ADDRESS=@':'',
                                                 })

def main():
    gmt, localt = utime.gmtime(), utime.localtime()
    assert gmt == localt
    task_list.load_tasks([{"from_day": [1, 1], "week_days": [], "name": "abajo",  "end": [0, 20, 0],
                                 "gate": 1, "start": [0, 0, 0], "to_day": [1, 2], "pump": 0},
                                {"from_day": [1, 1], "week_days": [], "name": "arriba", "end": [0, 10, 0],
                                 "gate": 0, "start": [0, 0, 0], "to_day": [1, 2], "pump": 0}])
    log.LOG_LEVEL = log.DEBUG
    log.garbage_collect()
    light.on()
    try:
        uasyncio.run(app.run())
        uasyncio.run(task_list.loop_tasks())
    finally:
        uasyncio.run(app.close())
        _ = uasyncio.new_event_loop()


if __name__ == '__main__':
    main()

