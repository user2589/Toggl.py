#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import urllib
import logging


class TogglException(IOError):
    """ Custom exception to indicate Toggl API errors"""
    pass


class Toggl(object):
    """ Class to access Toggl API

    API docs can be found at:
    https://github.com/toggl/toggl_api_docs/blob/master/reports.md
    """
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
            raise TogglException("""Error getting Toggl data:
            message: %(message)s
            tip: %(tip)s
            code: %(code)s""" % response_json['error'])

        return response_json

    def _request(self, api_func, params=None, filters=None):
        url = self._build_url(api_func, params)
        if filters is None:
            return self._get_json(url)
        return [i for i in self._get_json(url)
                if all(i.get(k) == v for k, v in filters.items())]

    def get_workspaces(self):
        """ Get the list of workspaces
        :returns 2-tuple list of workspaces: [(<name>, <id>), ...].
        """
        data = self._request('api/v8/workspaces')

        # filter out personal workspaces:
        return [(w['name'], w['id']) for w in data
                if 'personal' not in w['name'] and w['admin']]

    def get_workspace_users(self, workspace_id, **filters):
        """ Get the list of workspace users.
        :param workspace_id: toggle workspace id, obtained from get_workspaces
        :return: list of user dicts

        Example: Get list of active users:
            get_workspace_users(ws_id, active=True)

        More information on API call output:
            https://github.com/toggl/toggl_api_docs/blob/master/chapters/workspace_users.md
        """
        return [u for u in self._request(
            'api/v8/workspaces/{0}/workspace_users'.format(workspace_id),
            filters=filters)]

    def get_projects(self, workspace_id, **filters):
        """ Get projects information
        :param workspace_id: toggle workspace id, obtained from get_workspaces
        :return: list of active project dicts

        More information on API call output:
        https://github.com/toggl/toggl_api_docs/blob/master/chapters/workspaces.md#get-workspace-projects
        """
        return [p for p in self._request(
            'api/v8/workspaces/{0}/projects'.format(workspace_id),
            filters=filters)]

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

    def detailed_report(self, workspace_id, since, until):
        """ Toggl detailed report for a given team

        More information on API call output:
        https://github.com/toggl/toggl_api_docs/blob/master/reports/detailed.md#example
        """
        page = 1
        records_read = 0
        records = []
        while True:
            report_page = self._request('reports/api/v2/details', {
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
            records.extend(report_page['data'])

            records_read += report_page['per_page']
            page += 1

            if records_read >= report_page['total_count']:
                return records
