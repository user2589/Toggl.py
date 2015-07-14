#!/usr/bin/env python
# -*- coding: utf-8 -*-

# API docs can be found here
# https://github.com/toggl/toggl_api_docs/blob/master/reports.md

import argparse
import settings
import json
import urllib
import logging
import datetime

# Date format used in settings, messages and input parameters.
# Note it might be different from Toggl.date_format
_date_format = "%Y-%m-%d"


class Toggl(object):
    baseURL = 'https://toggl.com/'
    date_format = '%Y-%m-%d'  # YYYY-MM-DD

    def __init__(self, api_token):
        self.logger = logging.getLogger(__name__)
        self.api_token = api_token
        # HTTP Auth magic
        # TODO: replace with urllib2 opener
        chunks = self.baseURL.split("//", 1)
        if len(chunks) < 2:  # no https? in url
            chunks[:0] = 'https:',
        self.baseURL = ''.join((chunks[0], "//",
                                ":".join((self.api_token, 'api_token@')),
                                chunks[1]))

    def _build_url(self, api_func, params):
        # build ULR of API request, which looks like:
        # https://${base_url}/{api_func}?param1=foo&param2=bar
        query = '' if params is None else '?' + urllib.urlencode(params)
        url = ''.join((self.baseURL, api_func, query))
        self.logger.debug("_build_url: %s:" % url)
        return url

    def _get_json(self, url):
        try:
            response = urllib.urlopen(url)
        except IOError:
            self.logger.error('Failed to open url: %s' % url)
            raise
        response_text = response.read()
        self.logger.debug("Response from Toggl: %s" % response_text)
        response_json = json.loads(response_text)
        if 'error' in response_json:
            self.logger.error("""Error getting Toggl data:
            message: %(message)s
            tip: %(tip)s
            code: %(code)s""" % response_json['error'])
            raise
        return response_json

    def _request(self, api_func, params=None):
        url = self._build_url(api_func, params)
        return self._get_json(url)

    def get_workspaces(self):
        # get workspaces list
        data = self._request('api/v8/workspaces')

        # filter out personal workspaces:
        workspaces = [{'name': w['name'], 'id': w['id']} for w in data
                      if 'personal' not in w['name'] and w['admin']]

        # get number of people in workspace
        for workspace in workspaces:
            users = self._request(
                'api/v8/workspaces/%s/users' % workspace['id'])
            workspace['members'] = sum(
                [u['email'] not in settings.admin_emails for u in users])

        return workspaces

    def get_projects(self, workspace_id):
        data = self._request('api/v8/workspaces/%s/projects' % workspace_id)
        return data

    def weekly_report(self, workspace_id, since, until):
        """ Toggl weekly report for a given team """
        return self._request('reports/api/v2/weekly', {
            'workspace_id': workspace_id,
            'since': since.strftime(self.date_format),
            'until': until.strftime(self.date_format),
            'user_agent': 'github.com/user2589/Toggl.py',
            'order_field': 'title',
            # title/day1/day2/day3/day4/day5/day6/day7/week_total
            'display_hours': 'decimal',  # decimal/minutes
        })

    def detailed_report(self, workspace_id, since, until, page=1):
        """
        Toggl detailed report for a given team
        """
        return self._request('reports/api/v2/details', {
            'workspace_id': workspace_id,
            'since': since.strftime(self.date_format),
            'until': until.strftime(self.date_format),
            'user_agent': 'github.com/user2589/Toggl.py',
            'order_field': 'date',
            # date/description/duration/user in detailed reports
            'order_desc': 'off',  # on/off
            'display_hours': 'decimal',  # decimal/minutes
            'page': page
        })


def last_sunday(date):
    return date - datetime.timedelta(days=date.weekday() + 1)


def week_list(start_date, end_date):
    """ List of datetime tuples (monday, sunday) for every week in the interval
    """
    weeks = []
    sunday = last_sunday(start_date)
    while sunday < end_date:
        monday = sunday - datetime.timedelta(days=6)
        weeks.append((monday, sunday))
        sunday += datetime.timedelta(days=7)
    return weeks


if __name__ == '__main__':
    # parse parameters
    parser = argparse.ArgumentParser(
        description="Create weekly time report for CMU SE programm for the "
                    "past week. HTML printed to stdout")
    parser.add_argument('-d', '--date', help='system date override, YYYY-MM-DD')
    parser.add_argument('-v', '--verbose',
                        help="Verbose mode, 5 - extra verbose, "
                             "1 - mute, default: 3", default=3)
    args = parser.parse_args()

    # configure verboseness
    try:
        verboseness = max(1, 5 - int(args.verbose) * 1) * 10
    except ValueError:
        verboseness = 30
    logging.basicConfig(level=verboseness)

    if args.date is None:
        date = datetime.datetime.now()
        logging.debug("No date specified, using system date: %s",
                      date.strftime(_date_format))
    else:
        try:
            date = datetime.datetime.strptime(args.date, _date_format)
        except ValueError:
            parser.exit(1, "Invalid date\n")

    start_date = datetime.datetime.strptime(settings.start_date, _date_format)
    end_date = datetime.datetime.strptime(settings.end_date, _date_format)

    if date < start_date or date > end_date:
        parser.exit(1, "Date {0} is out of the {1}..{2} range.\n Check dates in"
                       " settings.py\n".format(
                           date.strftime(_date_format), settings.start_date,
                           settings.end_date))

    # create report
    report_builder = Toggl(settings.api_token)
    workspaces = report_builder.get_workspaces()

    logging.debug("Raw workspaces JSON:\n %s", json.dumps(workspaces))

    # super_report has 3 dimensions: weeks, course (aka project), and
    # team (aka workspace), i.e.:
    # for week in weeks:
    #    for course in courses:
    #        for team in teams:
    #            time = super_report[week][team][course]
    # week is a Monday of the reported week in _date_format
    # Later it will be converted to report_data (see below)
    super_report = {}

    weeks = week_list(start_date, end_date)
    week_names = [m.strftime(settings.report_date_format) for (m, s) in weeks]
    # courses not in settings.core counted as meta project, named after value
    # of settings.everything_else
    electives = settings.everething_else

    # for each team request reports up to 'date', build list of project and
    # aggregate stats

    for (monday, sunday) in weeks:

        if sunday > date:
            break
        week = monday.strftime(settings.report_date_format)
        super_report[week] = {}

        for workspace in workspaces:
            team = workspace['name']
            super_report[week][team] = {}
            super_report[week][team][electives] = 0
            report = report_builder.weekly_report(workspace['id'], monday,
                                                  sunday)

            for project in report['data']:

                # project['totals'] is in miliseconds
                # divide by 3600000 to convert to hours
                hours = float(project['totals'][-1]) / (
                    3600000 * workspace['members'])

                course = project['title']['project']
                if course in settings.core_courses:
                    super_report[week][team][course] = hours
                else:
                    super_report[week][team][electives] += hours

    logging.debug("Raw super_report JSON:\n %s", json.dumps(super_report))

    # super_report contains all the data we need, but it is not suitable for
    # rendering. here it will be converted to report_data, which will be
    # iterated this way:
    # report_data[course][team] = [week1, week2, week3...week12]

    team_names = [ws['name'] for ws in workspaces]
    report_data = {}

    for course in settings.core_courses + [electives]:

        for team in team_names:
            if any((w in super_report and
                    team in super_report[w] and
                    course in super_report[w][team] for w in week_names)):
                if course not in report_data:
                    report_data[course] = {}
                report_data[course][team] = []
                for week in week_names:
                    if week in super_report and team in super_report[week] and \
                            course in super_report[week][team]:
                        report_data[course][team].append(
                            round(super_report[week][team][course], 2))
                    else:
                        report_data[course][team].append(None)

    logging.debug("Raw report_data JSON:\n %s", json.dumps(report_data))

    course_names = [c for c in settings.core_courses + [electives] if
                    c in report_data]

    # generate report file
    template_vars = {
    }

    print settings.template
    print """<script>
    var week_labels = {week_labels};
    var report_data = {report_data};
    var teams = {teams};
    var courses = {courses};
    var timestamp = {timestamp};
        </script>"""    .format(
        courses=json.dumps(course_names),
        week_labels=json.dumps(week_names),
        report_data=json.dumps(report_data),
        teams=json.dumps(team_names),
        timestamp=json.dumps(datetime.datetime.now().strftime(
                             "%b %d %Y %I:%M%p"))
        )
