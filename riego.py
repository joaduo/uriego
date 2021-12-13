import gc
import log
import uasyncio
import utime
from machine import Pin

DAY_SECONDS = 86400
MEM_FREE_THRESHOLD=20000
PUMP_PIN_NUMBER=12
GATE_PIN_NUMBER=14
TASK_LOOP_WAIT_SEC=60


def mktime(year, month, mday, hour=0, minute=0, second=0, weekday=0, yearday=0):
    return utime.mktime((year, month, mday, hour, minute, second, weekday, yearday))


class Critical(Exception):
    ...


class Pump:
    def __init__(self, pump_pin_n=PUMP_PIN_NUMBER, valve_pin_n=GATE_PIN_NUMBER):
        self.pump_out = Pin(pump_pin_n, Pin.OUT)
        self.valve_out = Pin(valve_pin_n, Pin.OUT)
        self.preventive_stop()
    def value(self):
        return self.pump_out.value()
    def start(self, valve_value):
        if self.pump_out.value():
            self.preventive_stop()
            raise Critical('Pump already running')
        log.info('Start pump')
        self.valve_out.value(valve_value)
        self.pump_out.on()
    def preventive_stop(self):
        if self.pump_out.value():
            log.info('Preventive stop pump')
            self.pump_out.off()
    def stop(self):
        log.info('Stop pump')
        self.pump_out.off()
        # pump off means gates off (no power)
        self.valve_out.off() # we only save relay power
    def monitor(self, running):
        log.info('Monitoring running={running}', running=running)
        if running:
            if not self.pump_out.value():
                raise Critical('Not running?')
        else:
            if self.pump_out.value():
                self.preventive_stop()
                raise Critical('Still running?')


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
            log.debug('Outside the day ranges')
            return DAY_SECONDS, DAY_SECONDS
        if weekday not in self.week_days:
            # Not in the day of the week
            log.debug('Not in the day of the week')
            return DAY_SECONDS, DAY_SECONDS
        # Things are happening today
        day_start_t = mktime(year, month, mday, self.start.hour, self.start.minute, self.start.second)
        start_delta = day_start_t - t
        if start_delta < 0 and abs(start_delta) > threshold:
            log.debug('Negative delta')
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
    async def run(self, t, duration):
        if self.running:
            log.info('{name!r} already runnning', name=self.name)
            return
        self.running = True
        log.info('Running {name!r} at {t}', name=self.name, t=t)
        self.start()
        try:
            sleep_sec = self.monitoring_period
            remaining = duration
            while remaining > 0:
                if not self.running:
                    # someone shut things down
                    log.info('Premature stop of {name}', name=self.name)
                    self.stop()
                    break
                self.monitor_task()
                log.info('Running {name!r} remaining={remaining}',
                         name=self.name, remaining=remaining)
                await uasyncio.sleep(sleep_sec)
                remaining -= sleep_sec
            if self.running:
                await uasyncio.sleep(duration % sleep_sec)
        finally:
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
    def load_tasks(self, table_json):
        to_hms = lambda hms_str: tuple(int(s) for s in hms_str.split(':'))
        to_int_weekday = lambda dlist: sorted(self.weekday_to_int(d) for d in dlist)
        new_table = []
        pump = Pump()
        for tdict in table_json:
            start = TimePoint(*to_hms(tdict['start']))
            end = TimePoint(*to_hms(tdict['end']))
            week_days = to_int_weekday(tdict['week_days'])
            from_m, from_d = tdict['from_day'].split(',')
            from_day = Day(self.month_to_int(from_m), int(from_d))
            to_m, to_d = tdict['to_day'].split(',')
            to_day = Day(self.month_to_int(to_m), int(to_d))
            schedule = WeeklySchedule(start, end, week_days, from_day, to_day)
            t = RiegoTask(tdict['name'], schedule, pump, gate_num=tdict['gate'])
            new_table.append(t)
        self.table.clear()
        self.table += new_table
        self.table_json.clear()
        self.table_json += table_json
        garbage_collect()
    def weekday_to_int(self, d):
        try:
            d = int(d)
            assert 0 <= d <= 6
            return d
        except ValueError:
            return ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'
                    ].index(d.lower()[:3])
    def month_to_int(self, d):
        try:
            d = int(d)
            assert 0 < d <= 12
            return d
        except ValueError:
            return ['jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dic'
                    ].index(d.lower()[:3]) + 1
    async def visit_tasks(self, now, threshold=1):
        log.info('Visiting all tasks at {now}', now=utime.gmtime(now))
        min_start = DAY_SECONDS
        for t in self.table:
            start_delta, _ = t.start_end_deltas(now, threshold)
            if abs(start_delta) <= threshold:
                uasyncio.create_task(t.run(now, t.schedule.duration()))
            else:
                min_start = min(min_start, start_delta)
        return min_start
    async def manual_tasks(self, now, manual):
        log.info('Running manual={manual}', manual=manual)
        for t in self.table:
            if t.name in manual:
                duration = t.schedule.duration()
                log.info('Running {name!r} takes {duration}', name=t.name, duration=duration)
                uasyncio.create_task(t.run(now, duration))
                await uasyncio.sleep(duration)
    async def stop(self, names, all_=False):
        for t in self.table:
            if t.name in names or all_:
                log.info('Stopping {name!r}', name=t.name)
                t.stop()


def garbage_collect():
    orig_free = gc.mem_free()
    if orig_free < MEM_FREE_THRESHOLD:
        log.info('Freeing memory...')
        gc.collect()
        log.info('Memory it was {orig_free} and now {now_free}',
                     orig_free=orig_free, now_free=gc.mem_free())


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

