import gc
import devices
import log
import uasyncio
import utime
import machine


DAY_SECONDS = 86400
MEM_FREE_THRESHOLD=20000
PUMP_PIN_NUMBER=12
GATE_PIN_NUMBER=14
TASK_LOOP_WAIT_SEC=3


def mktime(year, month, mday, hour=0, minute=0, second=0, weekday=0, yearday=0):
    return utime.mktime((year, month, mday, hour, minute, second, weekday, yearday))


class Day:
    def __init__(self, month, day):
        self.month = month
        self.day = day
    def __lt__(self, other):
        return (self.month, self.day) < (other.month, other.day)
    def __ge__(self, other):
        return (self.month, self.day) >= (other.month, other.day)


class TimePoint:
    def __init__(self, hour, minute, second=0):
        self.hour = hour
        self.minute = minute
        self.second = second
    def __lt__(self, other):
        return (self.hour, self.minute, self.second) < (other.hour, other.minute, other.second)
    def __sub__(self, other):
        return self.to_int() - other.to_int()
    def to_int(self):
        return mktime(0, 0, 0, self.hour, self.minute, self.second, 0, 0) 


class WeeklySchedule:
    def __init__(self, start, end, week_days, from_day, to_day):
        self.start = start
        self.end = end
        self.week_days = week_days
        self.from_day = from_day
        self.to_day = to_day
    def duration(self):
        return self.end - self.start
    def start_end_deltas(self, t, threshold=1):
        (year, month, mday, _, _, _, weekday, _) = utime.gmtime(t)
        from_day = mktime(year, self.from_day.month, self.from_day.day)
        to_year = year + 1 if self.from_day >= self.to_day else year
        to_day = mktime(to_year, self.to_day.month, self.to_day.day)
        # We make the end day inclusive
        to_day += DAY_SECONDS
        if not (from_day <= t < to_day):
            # Outside the day ranges
            return DAY_SECONDS, DAY_SECONDS
        if weekday not in self.week_days:
            # Not in the day of the week
            return DAY_SECONDS, DAY_SECONDS
        # Things are happening today
        day_start_t = mktime(year, month, mday, self.start.hour, self.start.minute, self.start.second)
        start_delta = day_start_t - t
        if start_delta < 0 and abs(start_delta) > threshold:
            return DAY_SECONDS, DAY_SECONDS
        day_end_t = mktime(year, month, mday, self.end.hour, self.end.minute, self.end.second)
        end_delta = day_end_t - t
        assert end_delta > 0
        return start_delta, end_delta


class RiegoTask:
    monitoring_period = 10
    def __init__(self, name, schedule, pump, gate_num):
        self.name = name
        self.schedule = schedule
        self.pump = pump
        self.gate_num = gate_num
        self.running = False
    def start_end_deltas(self, t, threshold=1):
        return self.schedule.start_end_deltas(t, threshold)
    async def run(self):
        if self.running:
            return
        self.running = True
        log.info('Starting {}'.format(self.name))
        self.start()
        try:
            remaining = self.schedule.duration()
            while remaining > self.monitoring_period:
                if not self.running:
                    log.info('Premature stop of {name}', name=self.name)
                    self.stop()
                    break
                self.monitor_task()
                log.info('Running {name!r} remaining={remaining}',
                         name=self.name, remaining=remaining)
                await uasyncio.sleep(self.monitoring_period)
                remaining -= self.monitoring_period
            if self.running and remaining:
                await uasyncio.sleep(remaining)
        finally:
            log.info('Ending {}'.format(self.name))
            self.stop()
            self.monitor_task()
    def start(self):
        self.pump.start(self.gate_num)
    def stop(self):
        self.pump.stop()
        self.running = False
    def monitor_task(self):
        self.pump.monitor(running=self.running)


class TaskList:
    table = []
    table_json = []
    pump = devices.Pump()
    def load_tasks(self, table_json):
        new_table = []
        for tdict in table_json:
            schedule = WeeklySchedule(TimePoint(*tdict['start']),
                                      TimePoint(*tdict['end']),
                                      tdict['week_days'],
                                      Day(*tdict['from_day']),
                                      Day(*tdict['to_day']))
            t = RiegoTask(tdict['name'], schedule, self.pump, gate_num=tdict['gate'])
            new_table.append(t)
        self.table.clear()
        self.table += new_table
        self.table_json.clear()
        self.table_json += table_json
        garbage_collect()
    async def visit_tasks(self, now, threshold=1):
        log.info('Visiting all tasks at {now}', now=utime.gmtime(now))
        min_start = DAY_SECONDS
        for t in self.table:
            start_delta, _ = t.start_end_deltas(now, threshold)
            if abs(start_delta) <= threshold:
                uasyncio.create_task(t.run())
            else:
                min_start = min(min_start, start_delta)
        return min_start
    async def manual_tasks(self, manual):
        log.info('Running manual={manual}', manual=manual)
        name_task = {t.name:t for t in self.table if t.name in manual}
        for n in manual:
            t = name_task[n]
            uasyncio.create_task(t.run())
            # We run tasks serialized
            await uasyncio.sleep(t.schedule.duration())
            while t.running:
                # Wait for it to properly finish
                await uasyncio.sleep(1)
    async def stop(self, names, all_=False):
        for t in self.table:
            if t.name in names or all_:
                log.info('Stopping {name!r}', name=t.name)
                t.stop()


def garbage_collect():
    orig_free = gc.mem_free()
    if orig_free < MEM_FREE_THRESHOLD:
        print('Collecting garbage ori_free={}'.format(orig_free))
        gc.collect()
        log.info('Memory it was {orig_free} and now {now_free}',
                     orig_free=orig_free, now_free=gc.mem_free())


def init_devices():
    task_list.pump.stop()


task_list = TaskList()
manual_names = []
async def loop_tasks(threshold=1):
    assert threshold > 0
    max_wait = TASK_LOOP_WAIT_SEC
    garbage_collect()
    while True:
        if manual_names:
            manual = tuple(manual_names)
            manual_names.clear() # free the task queue
            await task_list.manual_tasks(manual)
        now = utime.time()
        (year, month, mday, hour, minute, second, weekday, yearday) = utime.gmtime(now)
        if year < 2021:
            log.info('RTC is wrong {now}', now=now)
            await uasyncio.sleep(max_wait)
            continue
        next_delta = await task_list.visit_tasks(now, threshold)
        tomorrow_delta = mktime(year, month, mday) + DAY_SECONDS - now
        wait_delta = min(min(next_delta, tomorrow_delta), max_wait)
        log.info('next_delta={next_delta}, tomorrow_delta={tomorrow_delta}, wait_delta={wait_delta}...',
                 next_delta=next_delta, tomorrow_delta=tomorrow_delta, wait_delta=wait_delta)
        await uasyncio.sleep(max(0, wait_delta - threshold))
        # We want to time how ms it takes
        start_ms = utime.ticks_ms()
        garbage_collect()
        delta_ms = utime.ticks_ms() - start_ms
        # then subtract it from the waiting time
        await uasyncio.sleep(max(threshold - delta_ms // 1000, 0))

