import os
import json
import re
import requests
import pprint
import datetime
import logging
import time
import functools
import hmac
import hashlib
import subprocess
import lib
import sys


log = logging.getLogger(__name__)

jenkins_uri = os.environ.get('JENKINS_URI', 'https://jenkinsci.saltstack.com/api/json')
log_level = os.environ.get('LOG_LEVEL', 'INFO')

github_user = os.environ['GITHUB_USER']
github_password = os.environ['GITHUB_PASSWORD']
git_key = os.environ['GIT_KEY']



def should_skip_pr(pull):
    if pull['base']['ref'] != 'master':
        return True
    if not pull['mergeable']:
        return True
    return False

def status_key(node):
    '''
    Return a sortable key for a pull request status
    '''
    return lib.parse_date(node['created_at'])

def handle_pull(pull, session):
    pr_url = pull['_links']['html']['href']
    api_pr_url = pull['_links']['self']['href']
    staturl = pull['_links']['statuses']['href']
    statuses = []
    while True:
        status_resp = session.get(staturl)
        statuses.extend(status_resp.json())
        links = lib.parse_links(status_resp.headers)
        if 'next' not in links:
            break
        staturl = links['next']
    seen_statuses = set()
    current_statuses = []
    for stat in sorted(statuses, key=status_key, reverse=True):
        if stat['context'] == 'codecov/project':
            continue
        if stat['context'] in seen_statuses:
            continue
        current_statuses.append(stat)
        seen_statuses.add(stat['context'])
    states = set()
    for stat in current_statuses:
        states.add(stat['state'])
    if len(states) == 1:
        state = states.pop()
        labels = ', '.join([a['name'] for a in pull['labels']])
        print(f"{pr_url} {state} {labels}")
        return True


def main():

    session = lib.authenticated_session(
        github_user,
        github_password,
        lib.get_otp(git_key)
    )

    pulls_url = 'https://api.github.com/repos/SaltStack/salt/pulls'
    count = 0
    max_count = 500

    # Test against a single PR
    #pr_resp = session.get('https://api.github.com/repos/SaltStack/salt/pulls/55140')
    #if pr_resp.status_code != 200:
    #    raise Exception(f"Bad response {pr_resp.status_code}")
    #pull = pr_resp.json()
    #handle_pull(pull, session)
    #return

    while True:
        if count >= max_count:
            break
        resp = session.get(pulls_url)
        if resp.status_code != 200:
            raise Exception(f"Bad response {resp.status_code}")
        for pull_light in resp.json():
            if count >= max_count:
                break
            pr_resp = session.get(pull_light['_links']['self']['href'])
            if pr_resp.status_code != 200:
                raise Exception(f"Bad response {pr_resp.status_code}")
            pull = pr_resp.json()
            if should_skip_pr(pull) is True:
                continue
            if handle_pull(pull, session):
                count += 1

        links = lib.parse_links(resp.headers)
        if 'next' not in links:
            break
        pulls_url = links['next']
    print("*" * 80)
    print("DONE")
    print("*" * 80)

if __name__ == '__main__':
    main()
