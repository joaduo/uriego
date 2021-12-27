import devices
import log
import schedule
import uasyncio
import utime
import machine


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
            log.info('Task already running {}'.format(self.name))
            return
        self.running = True
        log.info('Starting {}'.format(self.name))
        try:
            self.start()
            self.remaining = duration or self.schedule.duration()
            while self.remaining >= self.monitoring_period:
                if not self.running:
                    log.info('Premature stop of {name}', name=self.name)
                    break
                self.monitor_task()
                log.info('Running {name} remaining={remaining}',
                         name=self.name, remaining=self.remaining)
                await uasyncio.sleep(self.monitoring_period)
                self.remaining -= self.monitoring_period
            if self.running and self.remaining:
                await uasyncio.sleep(self.remaining)
        finally:
            log.info('Ending {}'.format(self.name))
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
    stop_manual = False
    manual_running = 0
    manual_queue = []
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
            self.manual_queue.clear()
            self.stop_manual = True
        for t in self.table:
            if t.name in names or all_:
                log.info('Stopping {name!r}', name=t.name)
                t.stop()


def init_devices():
    task_list.pump.stop()


task_list = TaskList()
async def loop_tasks(threshold=1):
    assert threshold > 0
    max_wait = TASK_LOOP_WAIT_SEC
    log.garbage_collect()
    while True:
        if task_list.manual_queue:
            await task_list.run_manual()
        now = utime.time()
        (year, month, mday, hour, minute, second, weekday, yearday) = utime.gmtime(now)
        # if year < 2021:
        #     log.info('RTC is wrong {now}', now=now)
        #     await uasyncio.sleep(max_wait)
        #     continue
        next_delta = await task_list.visit_tasks(now, threshold)
        tomorrow_delta = schedule.mktime(year, month, mday) + schedule.DAY_SECONDS - now
        wait_delta = min(min(next_delta, tomorrow_delta), max_wait)
        log.info('next_delta={next_delta}, tomorrow_delta={tomorrow_delta}, wait_delta={wait_delta}...',
                 next_delta=next_delta, tomorrow_delta=tomorrow_delta, wait_delta=wait_delta)
        await uasyncio.sleep(max(0, wait_delta - threshold))
        # We want to time how ms it takes
        start_ms = utime.ticks_ms()
        log.garbage_collect()
        delta_ms = utime.ticks_ms() - start_ms
        # then subtract it from the waiting time
        await uasyncio.sleep(max(threshold - delta_ms // 1000, 0))

