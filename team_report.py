#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import csv
from collections import defaultdict
import math


def std(values):
    avg = sum(values) / len(values)
    return math.sqrt(sum([(avg - v) ** 2 for v in values]) / len(values))


if __name__ == '__main__':
    # parse parameters
    parser = argparse.ArgumentParser(
        description="Take individual report CSV from stdin and prints team "
                    "report to stdout. \n"
                    "Typical usage:\n"
                    "   ./detailed_report.py | tee detailed_report.csv | "
                    "./individual_report.py 2> reporting_violations.csv | "
                    "tee individual_report.csv | ./team_report.py > team.csv")
    parser.add_argument('-i', '--input', default="-", nargs="?",
                        type=argparse.FileType('r'),
                        help='File to use as input, empty or "-" for stdin')
    parser.add_argument('-o', '--output', default="-",
                        type=argparse.FileType('w'),
                        help='Output filename, "-" or skip for stdout')
    args = parser.parse_args()

    # reader record = ['user', 'team', 'project', 'avg'] + week_names
    reader = csv.DictReader(args.input)
    # we need to keep weeks order for symbolic names
    week_names = reader.fieldnames[4:]

    # team_report[team][project][week_name] = hours
    team_report = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: 0)))

    # this structure is used to see how many members in each team
    team_members = defaultdict(set)
    # average time per project per user to see how balanced is the team effort
    # averages[team][project] = [ user1_avg, user2_avg, ...]
    averages = defaultdict(
        lambda: defaultdict(
            lambda: []))

    # first step: aggregate by teams and separate electives
    for record in reader:
        project = record['project']

        for i, week_name in enumerate(week_names):
            team_report[record['team']][project][week_name] += \
                float(record[week_name])

        averages[record['team']][project].append(float(record['average']))
        team_members[record['team']].add(record['user'])

    report_writer = csv.DictWriter(
        args.output, ['team', 'project', 'average', 'std'] + week_names)
    report_writer.writeheader()

    for team, team_records in team_report.items():
        for project, team_project_records in team_records.items():
            records = {
                week: round(team_project_records[week] / len(team_members[team]), 2)
                for week in week_names
                }
            records.update({
                'team': team,
                'project': project,
                'average': round(sum(records.values()) / len(records), 2),
                'std': round(std(records.values()), 2),
            })
            report_writer.writerow(records)
