import uasyncio
import utime
import gc
import logging

DAY_SECONDS = 60*60*24


def gmtime(t=None):
    return utime.gmtime()


def mktime(year, month, mday, hour=0, minute=0, second=0, weekday=0, yearday=0):
    return utime.mktime((year, month, mday, hour, minute, second, weekday, yearday))


def time():
    return utime.time()


class Day:
    def __init__(self, month, day):
        assert 0 < month <= 12, month
        assert 0 < day <= 31, day
        self.month = month
        self.day = day
    def __lt__(self, other):
        return (self.month, self.day) < (other.month, other.day)
    def __ge__(self, other):
        return (self.month, self.day) >= (other.month, other.day)


class TimePoint:
    def __init__(self, hour, minute, second=0):
        assert 0 <= hour <= 23, hour
        assert 0 <= minute <= 59, minute
        assert 0 <= second <= 59, second
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
        assert start < end, '%s < %s ' % (start, end)
        self.start = start
        self.end = end
        self.week_days = week_days
        self.from_day = from_day
        self.to_day = to_day
    def duration(self):
        return self.end - self.start
    def start_end_deltas(self, t, threshold=1):
        (year, month, mday, _, _, _, weekday, _) = gmtime(t)
        from_day = mktime(year, self.from_day.month, self.from_day.day)
        to_year = year + 1 if self.from_day >= self.to_day else year
        to_day = mktime(to_year, self.to_day.month, self.to_day.day)
        # We make the end day inclusive
        to_day += DAY_SECONDS
        if not (from_day <= t < to_day):
            # Outside the day ranges
            logging.debug('Outside the day ranges')
            return DAY_SECONDS, DAY_SECONDS
        if weekday not in self.week_days:
            # Not in the day of the week
            logging.debug('Not in the day of the week')
            return DAY_SECONDS, DAY_SECONDS
        # Things are happening today
        day_start_t = mktime(year, month, mday, self.start.hour, self.start.minute, self.start.second)
        start_delta = day_start_t - t
        if start_delta < 0 and abs(start_delta) > threshold:
            logging.debug('Negative delta')
            return DAY_SECONDS, DAY_SECONDS
        day_end_t = mktime(year, month, mday, self.end.hour, self.end.minute, self.end.second)
        end_delta = day_end_t - t
        assert end_delta > 0
        return start_delta, end_delta


class RiegoTask:
    monitoring_threshold = 10
    def __init__(self, name, schedule, pump, gate):
        self.name = name
        self.schedule = schedule
        self.gate = gate
        self.pump = pump
        self.running = False
    def start_end_deltas(self, t, threshold=1):
        return self.schedule.start_end_deltas(t, threshold)
    async def run(self, t, duration):
        if self.running:
            logging.info('{name!r} already runnning', name=self.name)
            return
        self.running = True
        logging.info('Running {name!r} at {t}', name=self.name, t=t)
        self.start()
        try:
            sleep_sec = self.monitoring_threshold
            remaining = duration
            for i in range(duration//sleep_sec):
                if not self.running:
                    # someone shut things down
                    logging.info('Premature stop of {name}', name=self.name)
                    break
                self.monitor_task()
                logging.info('Running {name!r} remaining={remaining}',
                         name=self.name, remaining=remaining)
                await uasyncio.sleep(sleep_sec)
                remaining -= sleep_sec
            await uasyncio.sleep(duration % sleep_sec)
        finally:
            self.stop()
            self.monitor_task()
    def start(self):
        self.gate.open()
        self.pump.start()
    def stop(self):
        self.pump.stop()
        self.gate.close()
        self.running = False
    def monitor_task(self):
        self.pump.monitor(running=self.running)
        self.gate.monitor(running=self.running)


class DummyOutput:
    def open(self):
        logging.info('Open')
    def close(self):
        logging.info('Close')
    def start(self):
        logging.info('Start')
    def stop(self):
        logging.info('Stop')
    def monitor(self, running):
        logging.info('Monitoring running={running}', running=running)


class TaskList:
    table = []
    table_json = []
    def load_tasks(self, table_json):
        to_hms = lambda hms_str: tuple(int(s) for s in hms_str.split(':'))
        to_int_weekday = lambda dlist: sorted(self.weekday_to_int(d) for d in dlist)
        new_table = []
        pump = gate = DummyOutput()
        for tdict in table_json:
            start = TimePoint(*to_hms(tdict['start']))
            end = TimePoint(*to_hms(tdict['end']))
            week_days = to_int_weekday(tdict['week_days'])
            from_m, from_d = tdict['from_day'].split(',')
            from_day = Day(self.month_to_int(from_m), int(from_d))
            to_m, to_d = tdict['to_day'].split(',')
            to_day = Day(self.month_to_int(to_m), int(to_d))
            schedule = WeeklySchedule(start, end, week_days, from_day, to_day)
            t = RiegoTask(tdict['name'], schedule, pump, gate)
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
            return 'mon tue wed thu fri sat sun'.split().index(d.lower()[:3])
    def month_to_int(self, d):
        try:
            d = int(d)
            assert 0 < d <= 12
            return d
        except ValueError:
            return 'jan feb mar apr jun jul aug sep oct nov dic'.split().index(d.lower()[:3]) + 1
    def dummy_table(self):
        (year, month, mday, hour, minute, second, weekday, yearday) = gmtime()
        pump = gate = DummyOutput()
        table = [RiegoTask('test',
                           WeeklySchedule(
                               TimePoint(hour,minute,second+2), TimePoint(hour,minute, second+10), 
                               [0,1,2,3,4,5,6],
                               Day(1,1), Day(1,1)),
                           pump, gate,
                           ),
                RiegoTask('test2',
                           WeeklySchedule(
                               TimePoint(hour,minute,second+5), TimePoint(hour,minute, second+30), 
                               [0,1,2,3,4,5,6],
                               Day(1,1), Day(1,1)),
                           pump, gate,
                           )
                ]
        self.table += table
    async def visit_tasks(self, now, threshold=1, manual=tuple()):
        logging.info('Visiting all tasks at {now}', now=gmtime(now))
        min_start = DAY_SECONDS
        for t in self.table:
            start_delta, end_delta = t.start_end_deltas(now, threshold)
            duration = end_delta - start_delta
            if abs(start_delta) <= threshold:
                uasyncio.create_task(t.run(now, duration))
            else:
                if t.name in manual:
                    uasyncio.create_task(t.run(now, t.schedule.duration()))
                min_start = min(min_start, start_delta)
        return min_start
    async def stop(self, names, all_=False):
        for t in self.table:
            if t.name in names or all_:
                logging.info('Stopping {name!r}', name=t.name)
                t.stop()


def garbage_collect():
    orig_free = gc.mem_free()
    if orig_free < 10000:
        logging.info('Freeing memory...')
        gc.collect()
        logging.info('Memory it was {orig_free} and now {now_free}',
                     orig_free=orig_free, now_free=gc.mem_free())


task_list = TaskList()
manual_names = []
async def loop_tasks(threshold=1):
    assert threshold > 0
    max_wait = 60 # 1 min
    garbage_collect()
    while True:
        now = time()
        (year, month, mday, hour, minute, second, weekday, yearday) = gmtime(now)
        next_delta = await task_list.visit_tasks(now, threshold, manual=tuple(manual_names))
        manual_names.clear()
        tomorrow_delta = mktime(year, month, mday) + DAY_SECONDS - now
        wait_delta = min(min(next_delta, tomorrow_delta), max_wait)
        logging.info('next_delta={next_delta}, tomorrow_delta={tomorrow_delta}, wait_delta={wait_delta}...',
                 next_delta=next_delta, tomorrow_delta=tomorrow_delta, wait_delta=wait_delta)
        await uasyncio.sleep(max(0, wait_delta - threshold))
        # We want to time how ms it takes
        start_ms = utime.ticks_ms()
        garbage_collect()
        delta_ms = utime.ticks_ms() - start_ms
        # then subtract it from the waiting time
        await uasyncio.sleep(max(threshold - delta_ms // 1000, 0))

