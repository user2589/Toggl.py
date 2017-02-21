#!/usr/bin/env python

"""
Export detailed report in CSV using Toggl API
"""

import argparse
import csv
import datetime
import logging

import settings
from toggl import Toggl


def week_list(s_date, e_date):
    """ List of datetime tuples (monday, sunday) for every week in the interval
    Weeks will be in ascending order
    """
    wl = []
    # get date of last sunday
    sun = s_date - datetime.timedelta(days=s_date.weekday() + 1)
    while sun < e_date:
        mon = sun - datetime.timedelta(days=6)
        wl.append((mon, sun))
        sun += datetime.timedelta(days=7)
    return wl


if __name__ == '__main__':
    # parse parameters
    parser = argparse.ArgumentParser(
        description="Export detailed report from Toggl workspace(s) to CSV."
                    "Input date retrieved using Toggl API, output is printed to"
                    "standard output.\n"
                    "Typical usage:\n"
                    "./detailed_report.py > detailed_report.csv")
    parser.add_argument('-o', '--output', default="-",
                        type=argparse.FileType('w'),
                        help='Output filename, "-" or skip for stdout')
    parser.add_argument('-d', '--date', help='system date override, YYYY-MM-DD')
    parser.add_argument('-v', '--verbose',  default=3,
                        help="Verboseness, 5: debug, 1: quiet, default: 3")
    parser.add_argument('-a', '--all', action='store_true',
                        help="Include records from disabled users (omitted by "
                             "default)")
    args = parser.parse_args()

    date_format = "%Y-%m-%d"
    start_date = settings.start_date
    end_date = settings.end_date

    try:  # verboseness
        verboseness = max(1, 5 - int(args.verbose) * 1) * 10
    except ValueError:
        verboseness = 30
    logging.basicConfig(level=verboseness)

    today = datetime.datetime.now()
    if args.date is None:
        logging.debug("No date specified, using system date: %s",
                      today.strftime(date_format))
    else:
        try:
            today = datetime.datetime.strptime(args.date, date_format)
        except ValueError:
            parser.exit(1, "Invalid date\n")

    if today < start_date:
        parser.exit(1, "Start date ({0}) has not yet come.\n Check dates in"
                       "the settings.py\n".format(start_date))

    # create report
    toggl = Toggl(settings.api_token)
    workspaces = [(w['name'], w['id']) for w in toggl.get_workspaces()]

    weeks = week_list(start_date, end_date)

    report_writer = csv.DictWriter(
        args.output, ['user', 'team', 'project', 'start', 'duration'])
    report_writer.writeheader()

    for (monday, sunday) in weeks:
        if sunday > today:
            break

        for ws_name, ws_id in workspaces:
            inactive_users = set() if args.all else \
                set(u['name'] for u in
                    toggl.get_workspace_users(ws_id, inactive=True))

            for record in toggl.detailed_report(ws_id, monday, sunday):
                # exclude inactive users
                if record['user'] in inactive_users:
                    continue

                # record duration is in milliseconds
                # divide by 3600000 to convert to hours
                report_writer.writerow({
                    'user': record['user'],
                    'team': ws_name,
                    'project': record['project'],
                    # example of record['start']: 2015-05-29T16:07:20+03:00
                    'start': record['start'][:19],
                    'duration': round(float(record['dur']) / 3600000, 2)
                })
