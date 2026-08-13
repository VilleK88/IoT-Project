import time
from machine import RTC

class TimeManager:
    def set_finland_local_time(self):
        utc_time = time.gmtime()

        if self._is_summer_time(utc_time):
            offset_seconds = 3 * 60 * 60
        else:
            offset_seconds = 2 * 60 * 60

        local_time = time.gmtime(
            time.time() + offset_seconds
        )

        rtc = RTC()

        rtc.datetime((
            local_time[0],  # year
            local_time[1],  # month
            local_time[2],  # day
            local_time[6],  # weekday
            local_time[3],  # hour
            local_time[4],  # minute
            local_time[5],  # second
            0  # subseconds
        ))

    def _days_in_month(self, year, month):
        if month == 2:
            if year % 400 == 0 or year % 4 == 0 and year % 100 != 0:
                return 29
            return 28
        if month in (4, 6, 9, 11):
            return 30
        return 31

    def _last_sunday(self, year, month):
        last_day = self._days_in_month(year, month)
        timestamp = time.mktime((year, month, last_day, 0, 0, 0, 0, 0))
        weekday = time.localtime(timestamp)[6]
        days_since_sunday = (weekday + 1) % 7
        return last_day - days_since_sunday

    def _is_summer_time(self, utc_time):
        year = utc_time[0]
        march_sunday = self._last_sunday(year, 3)
        october_sunday = self._last_sunday(year, 10)
        current = (
            utc_time[1],
            utc_time[2],
            utc_time[3],
            utc_time[4],
            utc_time[5]
        )
        summer_start = (
            3,
            march_sunday,
            1,
            0,
            0
        )
        summer_end = (
            10,
            october_sunday,
            1,
            0,
            0
        )
        return summer_start <= current < summer_end

    def timestamp(self):
        local = time.localtime()

        return (
            "{:04d}-{:02d}-{:02d} "
            "{:02d}:{:02d}:{:02d}"
        ).format(
            local[0], local[1], local[2],
            local[3], local[4], local[5]
        )