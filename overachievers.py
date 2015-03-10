#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import settings
import logging
import datetime
import csv
import sys
import report

fields = ['user', 'team', 'duration', 'project', 'date']

if __name__ =='__main__':
    parser = argparse.ArgumentParser(
        description='List time records longer than N hours (10 by default) in CSV format.')
    parser.add_argument('-d', '--date', help='system date override, YYYY-MM-DD')
    parser.add_argument('-n', '--threshold', type=int, default=10, help='time record threshold in hours')
    parser.add_argument('-v', '--verbose', help="Verbose mode, 5 - extra verbose, "
                        "1 - mute, default: 3", default = 3)
    args = parser.parse_args()

    # configure verboseness
    try:
        verboseness = max(1, 5 - int(args.verbose)*1) * 10
    except ValueError:
        verboseness = 30
    logging.basicConfig(level=verboseness)

    _date_format = report._date_format
    if args.date is None:
        date = datetime.datetime.now()
        logging.debug("No date specified, using system date: %s"%date.strftime(_date_format))
    else:
        try:
            date = datetime.datetime.strptime(args.date, _date_format)
        except ValueError:
            parser.exit(1, "Invalid date\n")

    start_date = datetime.datetime.strptime(settings.start_date, _date_format)
    end_date = datetime.datetime.strptime(settings.end_date, _date_format)

    if date < start_date or date > end_date:
        parser.exit(1, "Date (%s) is out of the %s..%s range.\n Check dates in settings.py\n"%(
                date.strftime(_date_format), settings.start_date, settings.end_date))

    #create report
    report_builder = report.Toggl(settings.api_token)
    workspaces = report_builder.get_workspaces()

    weeks = report.week_list(start_date, end_date)
    week_names = [m.strftime(settings.report_date_format) for (m, s) in weeks]

    writer = csv.DictWriter(sys.stdout, fields)
    writer.writeheader()

    # for each team request reports up to 'date', build list of project and aggregate stats

    for (monday, sunday) in weeks:

        if sunday > date:
            break
        week = monday.strftime(settings.report_date_format)

        for workspace in workspaces:
            report = report_builder.detailed_report(workspace['id'], monday, sunday)

            for record in report['data']:
                #record duration is in miliseconds, divide by 3600000 to convert to hours
                hours = float(record['dur'])/3600000
                if hours > args.threshold:
                    writer.writerow({
                        'user'    : record['user'],
                        'team'    : workspace['name'],
                        'duration': round(hours, 2),
                        'project' : record['project'],
                        'date'    : record['start'].split('T', 1)[0],
                        })

