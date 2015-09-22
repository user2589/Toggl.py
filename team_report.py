#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import settings
import json
import datetime
import sys
import csv
from collections import defaultdict

import detailed_report

if __name__ == '__main__':
    # parse parameters
    parser = argparse.ArgumentParser(
        description="Generate HTML report using template and detailed report "
                    "for the given period in CSV format. Input report read from"
                    " standard input, HTML report printed to stadard output.\n"
                    "To generate CSV report, use detailed_report.py. Typical "
                    "use:\n "
                    "Tipical usage:\n"
                    "   ./detailed_report.py | tee detailed_report.csv | "
                    "./individual_report.py 2> reporting_violations.csv | "
                    "tee individual_report.csv | ./team_report.py")
    args = parser.parse_args()

    start_date = datetime.datetime.strptime(settings.start_date,
                                            settings.date_format)
    end_date = datetime.datetime.strptime(settings.end_date,
                                          settings.date_format)

    weeks = detailed_report.week_list(start_date, end_date)
    week_names = [m.strftime(settings.report_date_format) for m, s in weeks]

    deviations = {}

    # reader record = ['user', 'team', 'project', 'avg'] + week_names
    reader = csv.DictReader(sys.stdin)

    # report_data[course][team] = [week1, week2, week3...week12]
    team_report = defaultdict(
        lambda: defaultdict(
            lambda: [None]*len(weeks)))

    # this structure is used to calculate average and standard deviation
    # aggregates[team][course][user] = value
    # - we need this default to sum up settings.everything_else into a single
    #   category
    user_average = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: 0)))

    # this structure is used to see how many members in each team
    team_members = defaultdict(set)

    # first step: aggregate by teams and separate electives
    for record in reader:
        project = record['project'] \
            if record['project'] in settings.core_courses \
            else settings.everything_else

        for i, week_name in enumerate(week_names):
            if week_name not in record:
                break  # end of collected data, leave rest to be None
            if team_report[project][record['team']][i] is None:
                team_report[project][record['team']][i] = 0
            team_report[project][record['team']][i] += \
                float(record[week_name])

        # in most cases we don't need this sum. It is here only for electives
        user_average[record['team']][project][record['user']] += \
            float(record['average'])

        team_members[record['team']].add(record['user'])

    # at this point team_report is just sum over team members
    # second step: normalize by team size
    for project, course_records in team_report.items():
        for team, course_team_records in course_records.items():
            team_report[project][team] = \
                [wh and round(wh / len(team_members[team]), 2)
                 for wh in course_team_records]

    # now, calculate average and variance for each team
    team_average = defaultdict(dict)
    variance = defaultdict(dict)
    for team, team_records in user_average.items():
        for project, team_course_records in team_records.items():
            team_average[project][team] = round(
                sum(user_average[team][project].values())
                / len(team_members[team]),
                2)

            variance[project][team] = round(
                sum([(team_average[project][team] - u)**2
                     for u in user_average[team][project].values()]
                    ) / max(len(team_members[team])-1, 1),
                2)

    projects = [c for c in settings.core_courses + [settings.everything_else]
               if c in team_report]

    print settings.template
    print """<script>
        var week_labels = {week_labels};
        var report_data = {report_data};
        var teams = {teams};
        var courses = {projects};
        var timestamp = {timestamp};
        var variance = {variance};
        var average = {average};
        </script>""".format(
        projects=json.dumps(projects),
        week_labels=json.dumps(week_names),
        report_data=json.dumps(team_report),
        teams=json.dumps(team_members.keys()),
        timestamp=json.dumps(
            datetime.datetime.now().strftime("%b %d %Y %I:%M%p")),
        variance=json.dumps(variance),
        average=json.dumps(team_average),
        )
