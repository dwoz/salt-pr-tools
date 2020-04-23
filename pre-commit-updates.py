import os
import requests
import pprint
import logging
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
    return False

def status_key(node):
    '''
    Return a sortable key for a pull request status
    '''
    return lib.parse_date(node['created_at'])

def handle_pull(pull, session):
    pr_url = pull['_links']['html']['href']
    sys.stderr.write("{}\n".format(pr_url))
    sys.stderr.flush()
    api_pr_url = pull['_links']['self']['href']

    status_resp = session.get(pull['_links']['statuses']['href'])
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
        if stat['context'] in seen_statuses:
            continue
        current_statuses.append(stat)
        seen_statuses.add(stat['context'])
    for stat in current_statuses:
        if stat['context'] == 'ci/pre-commit' and stat['state'] == 'error':
            url = stat['target_url'].replace('display/redirect', 'consoleText')
            try:
                resp = requests.get(url)
            except requests.exceptions.ConnectionError:
                sys.stderr.write(f"Jenkins connection failure {url}\n")
                sys.stderr.flush()
                return False
            if resp.status_code != 200:
                sys.stderr.write(f"Non 200 from {url} {resp.status_code}")
                sys.stderr.flush()
                return False
            if resp.text.split('\n')[-3].find('pre-commit not found') != -1:
                sys.stdout.write(pr_url + ' ')
                sys.stdout.flush()
                if pull['mergeable_state'] in ('dirty', 'unknown'):
                    sys.stdout.write('- Conflicts\n')
                    sys.stdout.flush()
                    return False
                elif pull['mergeable_state'] == 'draft':
                    sys.stdout.write('- Draft\n')
                    sys.stdout.flush()
                    return False
                update_url = '{}/update-branch'.format(api_pr_url)
                resp = session.put(
                    update_url,
                    json={'expected_head_sha': pull['head']['sha']},
                    headers={'Accept': 'application/vnd.github.lydian-preview+json'},
                )
                if resp.status_code != 202:
                    pprint.pprint(pull)
                    raise Exception(f"Unable to update PR branch {pr_url} {resp.status_code}")
                sys.stdout.write('- Updated\n')
                sys.stdout.flush()
                return True
    return False


def main():

    session = lib.authenticated_session(
        github_user,
        github_password,
        lib.get_otp(git_key)
    )

    pulls_url = 'https://api.github.com/repos/SaltStack/salt/pulls'
    count = 0
    max_count = 100

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
