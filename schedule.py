import uasyncio
import utime


DAY_SECONDS = 86400


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
    def enabled(self):
        return bool(self.week_days)
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

