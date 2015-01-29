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
    baseURL='https://toggl.com/'
    date_format = '%Y-%m-%d' #YYYY-MM-DD

    def __init__(self, api_token):
        self.logger = logging.getLogger(__name__)
        self.api_token = api_token
        # HTTP Auth magic
        # TODO: replace with urllib2 opener
        chunks = self.baseURL.split("//", 1)
        if len(chunks) < 2: #no https? in url
            chunks[:0] = 'https:',
        self.baseURL = ''.join((chunks[0], "//", ":".join((self.api_token, 'api_token@')), chunks[1]))

    def _build_url(self, api_func, params):
        # build ULR of API request, which looks like:
        # https://${base_url}/{api_func}?param1=foo&param2=bar
        query = '' if params is None else '?' + urllib.urlencode(params)
        url =  ''.join((self.baseURL, api_func, query))
        self.logger.debug("_build_url: %s:"%url)
        return url

    def _get_json(self, url):
        try:
            response = urllib.urlopen(url)
        except IOError:
            self.logger.error('Failed to open url: %s'%url)
            raise
        response_text = response.read()
        self.logger.debug("Response from Toggl: %s"%response_text)
        response_json = json.loads(response_text)
        if 'error' in response_json:
            self.logger.error("""Error getting Toggl data:
            message: %(message)s
            tip: %(tip)s
            code: %(code)s"""%response_json['error'])
            raise
        return response_json

    def _request(self, api_func, params=None):
        url = self._build_url(api_func, params)
        return self._get_json(url)

    def get_workspaces(self):
        #get workspaces list
        data = self._request('api/v8/workspaces')

        #filter out personal workspaces:
        workspaces = [{'name': w['name'], 'id': w['id']} for w in data \
                            if 'personal' not in w['name'] and w['admin']]

        #get number of people in workspace
        print "\n\n\n"
        for workspace in workspaces:
            users = self._request('api/v8/workspaces/%s/users'%workspace['id'])
            workspace['members'] = sum([u['email'] not in settings.admin_emails for u in users])

        return workspaces

    def get_projects(self, workspace_id):
        data = self._request('api/v8/workspaces/%s/projects'%workspace_id)


    def weekly_report(self, workspace_id, since, until):
        """
        Toggl weekly report for a given team
        """
        #TODO: to support students failing the program, check number of team members for every week
        return self._request('reports/api/v2/weekly', {
            'workspace_id'  : workspace_id,
            'since'         : since.strftime(self.date_format),
            'until'         : until.strftime(self.date_format),
            'user_agent' : 'github.com/user2589/Toggl.py',
            'order_field': 'title', #title/day1/day2/day3/day4/day5/day6/day7/week_total
            'display_hours': 'decimal', #decimal/minutes
        })


def last_sunday(date):
    return date - datetime.timedelta(days = date.weekday()+1)

def week_list(start_date, end_date):
    """
    returns list of datetime tuples (monday, sunday) for every week in requested interval
    """
    w = []
    sunday = last_sunday(start_date)
    while sunday < end_date:
        monday = sunday - datetime.timedelta(days=6)
        w.append((monday, sunday))
        sunday += datetime.timedelta(days=7)
    return w

def create_chart():
    """
    Build chart URL using Google Static Chart API
    https://developers.google.com/chart/image/docs/chart_params
    """
    {
        'cht' : 'lc', # lc = line chart
    }
    pass

if __name__ =='__main__':
    logging.basicConfig(level=logging.DEBUG)
    #parse parameters
    parser = argparse.ArgumentParser(description='Create weekly time report for CMU SE programm for the past week.'
            ' HTML printed to stdout')
    parser.add_argument('-d', '--date', help='system date override, YYYY-MM-DD')
    args = parser.parse_args()
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
    report_builder = Toggl(settings.api_token)
    #workspaces = report_builder.get_workspaces()
    workspaces = json.loads('[{"name": "MSE-MASRE", "members": 5, "id": 494382}, {"name": "MSE-Observability", "members": 6, "id": 494387}, {"name": "MSE-Trusted Tartans", "members": 6, "id": 494388}, {"name": "MSIT - Parallel Universe", "members": 3, "id": 772294}, {"name": "MSIT-Verticals", "members": 3, "id": 772306}, {"name": "MSIT-Quantum", "members": 3, "id": 772310}, {"name": "MSIT-The Ghost Riders", "members": 3, "id": 772312}, {"name": "MSIT-Zenith", "members": 3, "id": 772452}, {"name": "MSIT-ZEUS", "members": 2, "id": 772455}, {"name": "MSIT-Carpe Diem", "members": 3, "id": 772466}, {"name": "MSIT-ESE Robit", "members": 3, "id": 775104}, {"name": "MSIT-ESE-Robit2", "members": 3, "id": 777351}]')

    logging.debug("Raw workspaces JSON:\n %s"%json.dumps(workspaces))

    # super_report has 3 dimensions: weeks, course (aka project), and team (aka workspace), i.e.:
    # for week in weeks:
    #    for course in courses:
    #        for team in teams:
    #            time = super_report[week][team][course]
    # week is a Monday of the reported week in _date_format
    # Later it will be converted to report_data (see below)
    super_report = {}

    weeks = week_list(start_date, end_date)
    week_names = [m.strftime(settings.report_date_format) for (m, s) in weeks]
    # courses not in settings.core counted as meta project settings.everething_else
    electives = settings.everething_else

    # for each team request reports up to 'date', build list of project and aggregate stats
    """
    for (monday, sunday) in weeks:

        if sunday > date:
            break
        week = monday.strftime(settings.report_date_format)
        super_report[week] = {}

        for workspace in workspaces:
            team = workspace['name']
            super_report[week][team] = {}
            super_report[week][team][electives] = 0
            report = report_builder.weekly_report(workspace['id'], monday, sunday)

            for project in report['data']:

                #project['totals'] is in miliseconds, divide by 3600000 to convert to hours
                hours = float(project['totals'][-1])/(3600000*workspace['members'])

                course = project['title']['project']
                if course in settings.core_courses:
                    super_report[week][team][course] = hours
                else:
                    super_report[week][team][electives] += hours

    logging.debug("Raw super_report JSON:\n %s"%json.dumps(super_report))

    # super_report contains all the data we need, but it is not suitable for rendering.
    # here it will be converted to report_data, which will be iterated this way:
    # report_data[course][team] = [week1, week2, week3...week12]
    """
    super_report = json.loads('{"Jan 19": {"MSIT-ZEUS": {"17677 MSIT Project I": 3.0833333333333335, "17654 Analysis of Software Artifacts": 6.375, "electives": 4.392777777777778, "17655 Architectures for Software Systems": 12.175, "17657 Communication for Software Engineers II": 1.3333333333333333}, "MSIT-Verticals": {"17677 MSIT Project I": 5.716481481481481, "17654 Analysis of Software Artifacts": 8.933518518518518, "electives": 21.782962962962966, "17655 Architectures for Software Systems": 14.220462962962962, "17657 Communication for Software Engineers II": 1.4321296296296295}, "MSIT-ESE-Robit2": {"17677 MSIT Project I": 7.254814814814814, "17654 Analysis of Software Artifacts": 8.70324074074074, "electives": 11.854629629629631, "17655 Architectures for Software Systems": 9.60925925925926}, "MSIT - Parallel Universe": {"17677 MSIT Project I": 9.61287037037037, "17654 Analysis of Software Artifacts": 7.150092592592593, "electives": 10.443703703703703, "17655 Architectures for Software Systems": 15.591405185185184, "17657 Communication for Software Engineers II": 3.4923148148148146}, "MSIT-Zenith": {"17677 MSIT Project I": 9.847592592592592, "17654 Analysis of Software Artifacts": 3.38, "electives": 4.076666666666666, "17655 Architectures for Software Systems": 4.148240740740741, "17657 Communication for Software Engineers II": 1.4122222222222223}, "MSE-Observability": {"17654 Analysis of Software Artifacts": 10.356157407407407, "17657 Communication for Software Engineers II": 0.08888888888888889, "electives": 21.841157407407408, "17655 Architectures for Software Systems": 7.29837962962963, "17672 Software Development Studio II": 7.264166666666667}, "MSIT-Carpe Diem": {"17677 MSIT Project I": 15.45, "17654 Analysis of Software Artifacts": 10.694444444444445, "electives": 24.495, "17655 Architectures for Software Systems": 11.527777777777779, "17657 Communication for Software Engineers II": 2.388888888888889}, "MSIT-ESE Robit": {"17677 MSIT Project I": 1.6005555555555555, "17654 Analysis of Software Artifacts": 5.478425925925926, "electives": 2.602777777777778, "17655 Architectures for Software Systems": 6.363981481481481}, "MSIT-Quantum": {"17677 MSIT Project I": 4.802222222222222, "17654 Analysis of Software Artifacts": 8.100277777777778, "electives": 8.287314814814815, "17655 Architectures for Software Systems": 10.609166666666667, "17657 Communication for Software Engineers II": 2.229537037037037}, "MSE-MASRE": {"17654 Analysis of Software Artifacts": 10.627666666666666, "17657 Communication for Software Engineers II": 0.16005555555555556, "electives": 21.58533333333333, "17655 Architectures for Software Systems": 9.045055555555555, "17672 Software Development Studio II": 10.289777777777777}, "MSE-Trusted Tartans": {"17654 Analysis of Software Artifacts": 6.499583333333334, "electives": 18.02986111111111, "17655 Architectures for Software Systems": 9.760185185185184, "17672 Software Development Studio II": 11.166666666666666}, "MSIT-The Ghost Riders": {"17677 MSIT Project I": 14.30425925925926, "17654 Analysis of Software Artifacts": 11.236851851851851, "electives": 12.521574074074074, "17655 Architectures for Software Systems": 9.089814814814815, "17657 Communication for Software Engineers II": 2.220462962962963}}, "Jan 12": {"MSIT-ZEUS": {"17677 MSIT Project I": 3.0833333333333335, "17654 Analysis of Software Artifacts": 3.5833333333333335, "electives": 2.375, "17655 Architectures for Software Systems": 4.5, "17657 Communication for Software Engineers II": 1.0}, "MSIT-Verticals": {"17677 MSIT Project I": 1.9735185185185184, "17654 Analysis of Software Artifacts": 2.5417592592592593, "electives": 1.6647222222222222, "17655 Architectures for Software Systems": 2.026111111111111, "17657 Communication for Software Engineers II": 0.5393518518518519}, "MSIT-ESE-Robit2": {"electives": 0.000462962962962963, "17655 Architectures for Software Systems": 0.5787962962962963}, "MSIT - Parallel Universe": {"17677 MSIT Project I": 5.374537037037037, "17654 Analysis of Software Artifacts": 2.9897222222222224, "electives": 13.278148148148148, "17655 Architectures for Software Systems": 4.251203703703704, "17657 Communication for Software Engineers II": 1.4444444444444444}, "MSIT-Zenith": {"17677 MSIT Project I": 6.413981481481481, "17654 Analysis of Software Artifacts": 1.3333333333333333, "electives": 4.265462962962963, "17655 Architectures for Software Systems": 2.437962962962963, "17657 Communication for Software Engineers II": 0.9941666666666666}, "MSE-Observability": {"17654 Analysis of Software Artifacts": 4.132685185185185, "17657 Communication for Software Engineers II": 1.0988888888888888, "electives": 7.159675925925926, "17655 Architectures for Software Systems": 7.973611111111111, "17672 Software Development Studio II": 3.072962962962963}, "MSIT-Carpe Diem": {"17677 MSIT Project I": 8.0, "17654 Analysis of Software Artifacts": 9.541481481481481, "electives": 16.805555555555557, "17655 Architectures for Software Systems": 11.0, "17657 Communication for Software Engineers II": 1.8333333333333333}, "MSIT-ESE Robit": {"17677 MSIT Project I": 1.6444444444444444, "17654 Analysis of Software Artifacts": 4.111111111111111, "electives": 0, "17655 Architectures for Software Systems": 4.167129629629629}, "MSIT-Quantum": {"17677 MSIT Project I": 3.6944444444444446, "17654 Analysis of Software Artifacts": 2.2222222222222223, "electives": 8.46111111111111, "17655 Architectures for Software Systems": 3.7055555555555557, "17657 Communication for Software Engineers II": 1.0}, "MSE-MASRE": {"17654 Analysis of Software Artifacts": 5.274222222222222, "17657 Communication for Software Engineers II": 0.7025, "electives": 8.32311111111111, "17655 Architectures for Software Systems": 8.50611111111111, "17672 Software Development Studio II": 3.6357222222222223}, "MSE-Trusted Tartans": {"17654 Analysis of Software Artifacts": 5.693564814814815, "17657 Communication for Software Engineers II": 1.4722222222222223, "electives": 8.292685185185185, "17655 Architectures for Software Systems": 7.936481481481482, "17672 Software Development Studio II": 11.778472222222222}, "MSIT-The Ghost Riders": {"17677 MSIT Project I": 8.16212962962963, "17654 Analysis of Software Artifacts": 3.4444444444444446, "electives": 15.416759259259258, "17655 Architectures for Software Systems": 11.265925925925925, "17657 Communication for Software Engineers II": 1.4803703703703703}}}')

    team_names   = [ws['name'] for ws in workspaces]
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
                    if week in super_report and team in super_report[week] and course in super_report[week][team]:
                        report_data[course][team].append(round(super_report[week][team][course], 2))
                    else:
                        report_data[course][team].append(None)

    logging.debug("Raw report_data JSON:\n %s"%json.dumps(report_data))

    course_names = [c for c in settings.core_courses+[electives] if c in report_data]

    #generate report file
    template_vars = {
        'courses'       : json.dumps(course_names),
        'week_labels'   : json.dumps(week_names),
        'report_data'   : json.dumps(report_data),
        'teams'         : json.dumps(team_names)
    }

    print settings.template%template_vars
