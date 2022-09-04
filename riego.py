import uasyncio
import utime
import machine
import ujson
import network
import devices
import log
import schedule
import webserver

WIFI_BUTTON_PIN = 0
LIGHT_PIN = 2
TASK_LOOP_WAIT_SEC=10

class RiegoTask:
    monitoring_period = 10
    def __init__(self, name, schedule, pump, gate_num):
        self.name = name
        self.schedule = schedule
        self.pump = pump
        self.gate_num = gate_num
        self.running = False
        self.remaining = 0
    def enabled(self):
        return bool(self.schedule.enabled())
    def start_end_deltas(self, t, threshold=1):
        return self.schedule.start_end_deltas(t, threshold)
    async def run(self, duration=None):
        if self.running:
            log.info('Task already running {}', self.name)
            return
        self.running = True
        log.info('Starting {}', self.name)
        try:
            self.start()
            self.remaining = duration or self.schedule.duration()
            while self.remaining >= self.monitoring_period:
                if not self.running:
                    log.info('Premature stop of {}', self.name)
                    break
                self.monitor_task()
                log.info('Running {} remaining={}',
                         self.name, self.remaining)
                await uasyncio.sleep(self.monitoring_period)
                self.remaining -= self.monitoring_period
            if self.running and self.remaining:
                await uasyncio.sleep(self.remaining)
        finally:
            log.info('Ending {}', self.name)
            self.stop()
            self.monitor_task()
    def start(self):
        assert self.pump.start(self.gate_num)
    def stop(self):
        self.pump.stop()
        self.running = False
        self.remaining = 0
    def monitor_task(self):
        self.pump.monitor(running=self.running)


class TaskList:
    table = []
    table_json = []
    pump = devices.Pump()
    manual_queue = []
    def __init__(self, wifi_tracker):
        self.wifi_tracker = wifi_tracker
        self.pump.stop()
    def load_tasks(self, table_json):
        new_table = []
        for tdict in table_json:
            sched = schedule.WeeklySchedule(
                    schedule.TimePoint(*tdict['start']),
                    schedule.TimePoint(*tdict['end']),
                    tdict['week_days'],
                    schedule.Day(*tdict['from_day']),
                    schedule.Day(*tdict['to_day']),
                    )
            t = RiegoTask(tdict['name'], sched, self.pump, gate_num=tdict['gate'])
            new_table.append(t)
        self.table.clear()
        self.table += new_table
        self.table_json.clear()
        self.table_json += table_json
        log.garbage_collect()
    async def loop_tasks(self, threshold=1):
        assert threshold > 0
        max_wait = TASK_LOOP_WAIT_SEC
        log.garbage_collect()
        while True:
            if self.manual_queue:
                await self.run_manual()
            now = utime.time()
            (year, month, mday, hour, minute, second, weekday, yearday) = utime.gmtime(now)
            # if year < 2021:
            #     log.info('RTC is wrong {now}', now=now)
            #     await uasyncio.sleep(max_wait)
            #     continue

            # if switching wifi ap <> client, will reset the esp
            if self.wifi_tracker.will_switch_wifi():
                machine.reset()
            next_delta = await self.visit_tasks(now, threshold)
            tomorrow_delta = schedule.mktime(year, month, mday) + schedule.DAY_SECONDS - now
            wait_delta = min(min(next_delta, tomorrow_delta), max_wait)
            log.info('next_delta={}, tomorrow_delta={}, wait_delta={}...',
                     next_delta, tomorrow_delta, wait_delta)
            await uasyncio.sleep(max(0, wait_delta - threshold))
            # We want to time how ms it takes
            start_ms = utime.ticks_ms()
            log.garbage_collect()
            delta_ms = utime.ticks_ms() - start_ms
            # then subtract it from the waiting time
            await uasyncio.sleep(max(threshold - delta_ms // 1000, 0))
    async def visit_tasks(self, now, threshold=1):
        log.info('Visiting all tasks at {now}', now=utime.gmtime(now))
        min_start = schedule.DAY_SECONDS
        for t in self.table:
            if not t.enabled():
                continue
            start_delta, _ = t.start_end_deltas(now, threshold)
            if abs(start_delta) <= threshold:
                uasyncio.create_task(t.run())
            else:
                min_start = min(min_start, start_delta)
        return min_start
    async def run_manual(self):
        name_task = {t.name:t for t in self.table}
        while self.manual_queue:
            n,cfg = self.manual_queue.pop()
            if n in name_task:
                t = name_task[n]
                if cfg.get('in_parallel'):
                    uasyncio.create_task(t.run(duration=cfg.get('duration')))
                else:
                    await t.run(duration=cfg.get('duration'))
    async def stop(self, names=tuple(), all_=False):
        if self.manual_queue:
            if all_:
                self.manual_queue.clear()
            else:
                new_queue = [(n,cfg) for n, cfg in self.manual_queue
                             if n not in names]
                self.manual_queue.clear()
                self.manual_queue.extend(new_queue)
        for t in self.table:
            if t.name in names or all_:
                log.info('Stopping {name!r}', name=t.name)
                t.stop()


class WifiTracker:
    def __init__(self,
                 client_essid,
                 client_password,
                 ap_essid,
                 ap_password,
                 ap_channel=4,
                 ap_network_mode=network.MODE_11B,
                 is_ap=True,
                 ):
        self.allow_set = {'client_essid',
                        'client_password',
                        'ap_essid',
                        'ap_password',
                        'ap_channel',
                        'ap_network_mode',
                        'is_ap',
                        }
        self.client_essid = client_essid
        self.client_password = client_password
        self.ap_essid = ap_essid
        self.ap_password = ap_password
        self.ap_channel = ap_channel
        self.ap_network_mode = ap_network_mode
        self.is_ap = is_ap
        self.schedule_switch = False
        self.light = machine.Pin(LIGHT_PIN, machine.Pin.OUT)
        self.button = devices.InvertedPin(WIFI_BUTTON_PIN, machine.Pin.IN)
        self.cfg_path = './wifi.json'
        for name, value in self.load_cfg().items():
            if name in self.allow_set:
                setattr(self, name, value)
        self.setup_wifi(self.is_ap)
    def json_set(self, cfg):
        for name, value in cfg.items():
            if name in self.allow_set and ('password' not in name or value):
                setattr(self, name, value)
    def json_get(self, shadow_passwords=True):
        cfg = {}
        for n in self.allow_set:
            v = getattr(self, n)
            if shadow_passwords and 'password' in n:
                v = ''
            cfg[n] = v
        return cfg
    def load_cfg(self):
        cfg = {}
        if webserver.file_exists(self.cfg_path):
            with open(self.cfg_path) as fp:
                cfg = ujson.load(fp)
        return cfg
    def dump_cfg(self):
        with open(self.cfg_path, 'w') as fp:
            ujson.dump(self.json_get(shadow_passwords=False), fp)
    def setup_wifi(self, attempts=10, wait=5):
        self.ap = ap = network.WLAN(network.AP_IF)
        self.wlan = wlan = network.WLAN(network.STA_IF)
        if self.is_ap:
            wlan.active(False)
            ap.config(essid=self.ap_essid,
                      password=self.ap_password,
                      channel=self.ap_channel,
                      authmode=network.AUTH_WPA_WPA2_PSK,
                      )
            network.phy_mode(self.ap_network_mode)
            ap.active(True)
            log.important('ap: {}', ap.ifconfig())
        else:
            ap.active(False)
            wlan.active(True)
            if not wlan.isconnected():
                log.info('connecting to {!r} network...', self.client_essid)
                wlan.connect(self.client_essid, self.client_password)
                while not wlan.isconnected() and attempts:
                    log.info('connecting to {!r} network {} more attemps to go...',
                             self.client_essid, attempts - 1)
                    attempts -= 1
                    utime.sleep(wait)
            utime.sleep(3)
            log.important('wlan: {}', wlan.ifconfig())
    def will_switch_wifi(self):
        if self.schedule_switch or self.button.value():
            log.debug('Waiting http request to close...')
            utime.sleep(1)
            if not self.schedule_switch:
                self.is_ap = not self.is_ap
            self.dump_cfg()
            self.schedule_switch = False
            return True
    async def blink(self):
        self.light.off()
        await uasyncio.sleep(0.2)
        if not self.schedule_switch:
            self.light.on()

def main():
    wt = WifiTracker('patio', '12343214', 'riego5', 'asd09ur9hasio9ykmzx')
    #wt = WifiTracker('usolar', 'LAMPARAalibaba', 'riego5', 'asd09ur9hasio9ykmzx', is_ap=False)

if __name__ == '__main__':
    main()

