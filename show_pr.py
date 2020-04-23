import os
import sys
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


log = logging.getLogger(__name__)

jenkins_uri = os.environ.get('JENKINS_URI', 'https://jenkinsci.saltstack.com/api/json')
#user = os.environ['JENKINS_USER']
#password = os.environ['JENKINS_PASS']
#github_secret = os.environ['GITHUB_SECRET']
log_level = os.environ.get('LOG_LEVEL', 'INFO')

github_user = os.environ['GITHUB_USER']
github_password = os.environ['GITHUB_PASSWORD']
git_key = os.environ['GIT_KEY']

def status_key(node):
    '''
    Return a sortable key for a pull request status
    '''
    return lib.parse_date(node['created_at'])

def main():
    session = lib.authenticated_session(
        github_user,
        github_password,
        lib.get_otp(git_key)
    )
    for pull_id in sys.argv[1:]:
        pull_url = f'https://api.github.com/repos/SaltStack/salt/pulls/{pull_id}'
        resp = session.get(pull_url)
        data = resp.json()
        pprint.pprint(data)
        status_resp = session.get(data['_links']['statuses']['href'])
        seen_statuses = set()
        current_statuses = []
        for stat in sorted(status_resp.json(), key=status_key, reverse=True):
            if stat['context'] in seen_statuses:
                continue
            current_statuses.append(stat)
            seen_statuses.add(stat['context'])
            #print(stat['context'], stat['state'])
        for stat in current_statuses:
            print(stat['context'], stat['state'])
            if stat['context'] == 'ci/pre-commit':
                pprint.pprint(stat)
                url = stat['target_url'].replace('display/redirect', 'consoleText')
                resp = session.get(url)
                if resp.text.split('\n')[-3].find('pre-commit not found') != -1:
                    print("NEEDS UPDATE")
                break
            #pprint.pprint(stat)
#        print(prstuff.should_skip_pr(data))
#        print(data['mergeable'] is False)
#        print(repr(data['mergeable']))

if __name__ == '__main__':
    main()

