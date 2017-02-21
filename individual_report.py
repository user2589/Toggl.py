#!/usr/bin/env python

import argparse
import csv
import datetime
import sys
from collections import defaultdict

import settings

detailed_report_date_format = "%Y-%m-%dT%H:%M:%S"


def week(date_str):
    d = datetime.datetime.strptime(date_str, detailed_report_date_format)
    d -= datetime.timedelta(days=d.weekday())
    return d.strftime(settings.report_date_format)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Generate individual report CSV from detailed report CSV. "
                    "Detailed report CSV accepted from standard input, "
                    "individual report printed to stadard output.\n Detailed "
                    "report entries also validated, validation notes printed to"
                    " stderr.\n"
                    "Typical usage:\n"
                    "   ./detailed_report.py | tee detailed_report.csv | "
                    "./individual_report.py > individual_report.csv 2> "
                    "reporting_violations.csv")
    parser.add_argument('-i', '--input', default="-", nargs="?",
                        type=argparse.FileType('r'),
                        help='File to use as input, empty or "-" for stdin')
    parser.add_argument('-o', '--output', default="-",
                        type=argparse.FileType('w'),
                        help='Output filename, "-" or skip for stdout')
    parser.add_argument('-n', '--threshold', type=int, default=10,
                        help='time record threshold in hours')
    args = parser.parse_args()

    # helper variables
    last_records = {}
    week_names = []

    # individual_report[user][team][project][week_name] = hours
    individual_report = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(lambda: 0))))

    # record.keys() = ['user', 'team', 'project', 'start', 'duration']
    reader = csv.DictReader(args.input)

    err_writer = csv.DictWriter(
        sys.stderr, ['user', 'team', 'duration', 'project', 'date', 'rule'])
    err_writer.writeheader()

    for record in reader:
        week_name = week(record['start'])
        if not week_names or week_names[-1] != week_name:
            week_names.append(week_name)

        hours = float(record['duration'])
        # example of record['start'] = 2015-05-29T16:07:20
        record_date = record['start'][:10]
        # -1 minute is to compensate for round error in conversion to hours
        # this duration is only used to check for overlapping entries and
        # should not affect overall statistics
        duration = datetime.timedelta(hours=hours, minutes=-1)
        end = datetime.datetime.strptime(
            record['start'], detailed_report_date_format) + duration
        record['end'] = end.strftime(detailed_report_date_format)
        user = record['user']
        project = record['project']
        team = record['team']

        # TIME LOGGING SANITY CHECK
        # long records, missing project, overlapping

        # missing project
        if not project:
            record['project'] = project = '(no project)'
            err_writer.writerow({
                'user': user,
                'team': team,
                'rule': 'record without project',
                'duration': hours,
                'project': project,
                'date': record_date,
            })

        # check for overlapping entry
        if user in last_records and \
                last_records[user]['end'] > record['start']:
            err_writer.writerow({
                'user': user,
                'team': team,
                'rule': 'overlaps: %(start)s %(project)s' % record,
                'duration': hours,
                'project': project,
                'date': record_date,
            })
            if record['end'] > last_records[user]['end']:
                last_records[user] = record
        else:
            last_records[user] = record

        # long records
        if hours > args.threshold:
            err_writer.writerow({
                'user': user,
                'team': team,
                'rule': 'record > %s hours' % args.threshold,
                'duration': hours,
                'project': project,
                'date': record_date,
            })

        individual_report[user][team][project][week_name] += hours

    # Now we'll aggregate stats, calculate average etc
    report_writer = csv.DictWriter(
        args.output, ['user', 'team', 'project', 'average'] + week_names)
    report_writer.writeheader()

    for user, user_records in individual_report.items():
        for team, user_team_records in user_records.items():
            for project, user_team_project_records in user_team_records.items():
                records = {
                    week: round(user_team_project_records[week], 2)
                    for week in week_names
                }
                average = sum(records.values()) / len(records)
                records.update({
                    'user': user,
                    'team': team,
                    'project': project,
                    'average': round(average, 2),
                })
                report_writer.writerow(records)
