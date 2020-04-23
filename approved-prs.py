import os
import re
import requests
import pprint
import logging
import lib


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
    if 'Needs Testcase' in [a['name'] for a in pull['labels']]:
        return True
    return False


def handle_pull(pull, session):
    pr_url = pull['_links']['html']['href']
    aprvs = lib.approvals(pull, session)
    if aprvs:
        approvers = []
        for apr in aprvs:
            approvers.append(apr['user']['login'])
        print(f"{pr_url} - {','.join(approvers)} - {pull['mergeable']}")
#    else:
#        print(f"{pr_url} - {pull['mergeable']}")


def main():

    session = lib.authenticated_session(
        github_user,
        github_password,
        lib.get_otp(git_key)
    )

    pulls_url = 'https://api.github.com/repos/SaltStack/salt/pulls'

    while True:
        resp = session.get(pulls_url)
        if resp.status_code != 200:
            raise Exception(f"Bad response {resp.status_code}")
        for pull_light in resp.json():
            pr_resp = session.get(pull_light['_links']['self']['href'])
            if pr_resp.status_code != 200:
                raise Exception(f"Bad response {pr_resp.status_code}")
            pull = pr_resp.json()
            if should_skip_pr(pull) is True:
                continue
            handle_pull(pull, session)

        links = lib.parse_links(resp.headers)
        if 'next' not in links:
            break
        pulls_url = links['next']

if __name__ == '__main__':
    main()
