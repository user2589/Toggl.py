#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import settings
import logging
import datetime
import csv
import sys
import report

from collections import defaultdict

if __name__ =='__main__':
    parser = argparse.ArgumentParser(
        description='List time records longer than N hours (10 by default) in CSV format.')
    parser.add_argument('-d', '--date', help='system date override, YYYY-MM-DD')
    parser.add_argument('-n', '--threshold', type=int, default=10, help='time record threshold in hours')
    parser.add_argument('-v', '--verbose', help="Verbose mode, 5 - extra verbose, "
                        "1 - mute, default: 3", default=3)
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
        logging.debug("No date specified, using system date: %s", date.strftime(_date_format))
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

    err_writer = csv.DictWriter(sys.stderr, ['user', 'team', 'duration', 'project', 'date', 'rule'])
    err_writer.writeheader()
    last_records = {} # last_records[user] = last_record

    # super_report[team][user][course][week]
    super_report = defaultdict(
                    lambda: defaultdict(
                        lambda: defaultdict(
                            lambda: defaultdict(lambda: 0))))

    week_names = []

    for (monday, sunday) in weeks:
        if sunday > date:
            break
        week = monday.strftime(settings.report_date_format)
        week_names.append(week)

        for workspace in workspaces:
            records_read = 0
            page = 1
            while True:
                report = report_builder.detailed_report(workspace['id'], monday, sunday, page)

                for record in report['data']:
                    #record duration is in miliseconds, divide by 3600000 to convert to hours
                    hours = round(float(record['dur'])/3600000, 2)
                    start = record['start'].split('T', 1)[0]

                    # TIME LOGGING SANITY CHECK - long records, missing project, overlapping

                    # missing project
                    if not record['project']: # usually None, but want to detect empty string as well
                        record['project'] = '(no project)'
                        err_writer.writerow({
                            'user'    : record['user'],
                            'team'    : workspace['name'],
                            'rule'    : 'record without project',
                            'duration': hours,
                            'project' : record['project'],
                            'date'    : start,
                            })

                    # check for overlapping entry
                    if record['user'] in last_records and last_records[record['user']]['end'] > record['start']:
                        err_writer.writerow({
                            'user'    : record['user'],
                            'team'    : workspace['name'],
                            'rule'    : 'overlapping entry: %(start)s %(project)s'%record,
                            'duration': hours,
                            'project' : record['project'],
                            'date'    : start,
                            })
                    last_records[record['user']] = record

                    # long records
                    if hours > args.threshold:
                        err_writer.writerow({
                            'user'    : record['user'],
                            'team'    : workspace['name'],
                            'rule'    : 'record > %s hours'% args.threshold,
                            'duration': hours,
                            'project' : record['project'],
                            'date'    : start,
                            })

                    # ACTUAL REPORTING
                    super_report[workspace['name']][record['user']][record['project']][week] = \
                        round(super_report[workspace['name']][record['user']][record['project']][week] + hours, 2)

                records_read += report['per_page']
                page += 1
                if records_read >= report['total_count']:
                    break

    report_writer = csv.DictWriter(sys.stdout, ['user', 'team', 'project', 'avg'] + week_names)
    report_writer.writeheader()

    for team, team_records in super_report.items():
        for user, user_records in team_records.items(): # user_records = super_report[team][user]
            for project, project_records in user_records.items(): # project_records = super_report[team][user][project]
                average = sum(project_records.values()) / len(project_records)
                project_records.update({
                    'user' : user,
                    'team' : team,
                    'project': project,
                    'avg'  : round(average, 2),
                })
                report_writer.writerow(project_records)

