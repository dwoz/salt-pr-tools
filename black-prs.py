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
log_level = os.environ.get('LOG_LEVEL', 'INFO')
log.setLevel(log_level)

github_user = os.environ['GITHUB_USER']
github_password = os.environ['GITHUB_PASSWORD']
git_key = os.environ['GIT_KEY']


def should_skip_pr(pull):
    if pull['base']['ref'] != 'master':
        return True
    if not pull['mergeable']:
        return True
    return False


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
    for stat in sorted(statuses, key=lib.status_key, reverse=True):
        if stat['context'] == 'codecov/project':
            continue
        if stat['context'] in seen_statuses:
            continue
        current_statuses.append(stat)
        seen_statuses.add(stat['context'])
    for stat in current_statuses:
        if stat['context'] == 'ci/pre-commit':
            if stat['state'] == 'pending':
                print('pre commit pending')
                return False
            elif stat['state'] == 'success':
                print('pre commit success')
                return False
            else:
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
            print(pull['_links']['html']['href'])
            if handle_pull(pull, session):
                if 'maintainer_can_modify' not in pull or pull['maintainer_can_modify'] is False:
                    print("PR can not be modified")
                    continue
                print('black pr')
                lib.black_pr(pull['number'], session)
                count += 1
        links = lib.parse_links(resp.headers)
        if 'next' not in links:
            break
        pulls_url = links['next']


if __name__ == '__main__':
    main()
