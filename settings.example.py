
from __future__ import print_function
from datetime import datetime, timedelta

# TODO: move to environment variable
api_token = 'yourapitokenhere'

# TODO: replace with init script called from a cronjob
PERIOD_TYPES = {
    # period type: (period1_start, period2_start, ...)  # str in %m%d format
    'quarter': ("0101", "0401", "0701", "1001"),
    'semester': ("0117", "0521", "0825"),
}


def automatic_dates(period_type, now=None, report_weekday=0):
    """ Calculate start_date and end_date from current timestamp automatically
    :param period_type: string, 'auarter' or 'semester'
    :param now: date of calculations (datetime.now() by default)
    :param report_weekday: weekday when report is updated. 0=Monday, 6=Sunday
    :return: (start_date, end_date)
    """
    if now is None:
        now = datetime.now()
    date = now.strftime("%m%d")
    if period_type not in PERIOD_TYPES:
        raise ValueError("automatic dates only support {} periods so far."
                         "".format(','.join(PERIOD_TYPES)))

    def calc(pstart, start_year):
        """ return first %weekday of the start date """
        start_date = datetime(start_year, int(pstart[:2]), int(pstart[2:4]))
        start_date += timedelta(
            days=(7 + report_weekday - start_date.weekday()) % 7)
        return start_date

    periods = PERIOD_TYPES[period_type]
    for i, end in enumerate(periods):
        start = periods[i-1]
        if date < end < start:
            # period stretches over the New Year, the date is after NY
            return calc(start, now.year - 1)
        elif end < start <= date:
            # period stretches over the New Year, the date is before NY
            return calc(start, now.year)
        elif start <= date < end:
            return calc(start, now.year)

# start_date is a date of first report. I.e. to get first report for Jan 5-11,
# first date should be Jan 12
start_date = automatic_dates('quarter')
# start_date = datetime(2017, 1, 30)

# Format string for date date representation in report,
# https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior
report_date_format = "%b %d"

if __name__ == '__main__':
    print ("""Settings:
    start_date: {start_date}
    """.format(**locals()))
