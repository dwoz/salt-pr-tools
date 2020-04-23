import os
import subprocess
import time
import requests
import datetime


def authenticated_session(github_user=None, github_password=None, otp=None, token_path='.git-token'):
    token = None
    session = requests.Session()
    if os.path.exists(token_path):
        with open(token_path, 'r') as fp:
            token = fp.read().strip()
    if not token:
        token = get_token(session, github_user, github_password, otp)
        with open(token_path, 'w') as fp:
            os.chmod(token_path, 0o600)
            fp.write(token)
    session.headers['Authorization'] = f'token {token}'
    return session


def get_otp(gitkey):
    '''
    Get a github 2FA token
    '''
    cmd = f"oathtool --totp -b {gitkey}"
    output=subprocess.check_output(cmd, shell=True)
    return output.decode().strip()


def print_prs(data, s):
    '''
    Print pull requests
    '''
    for i in data:
        print_pr(i, s)
        break

def print_pr(data, s):
    '''
    Print a pull request
    '''
    print('*' * 80)
    pprint.pprint(data)
    b = s.get(data['statuses_url'])
    for c in b.json():
        #print('*' * 80)
        print(c['context'])
        #print('-' * 80)
        #pprint.pprint(c)


def parse_links(headers):
    '''
    Parse the paging links from a github api response
    '''
    link_data = {}
    if 'link' in headers:
        links = [a.strip() for a in headers['link'].split(',')]
        for link in links:
            link, rel = [_.strip() for _ in link.split(';')[:2]]
            link = link.strip('<').strip('>')
            name = rel.split('=')[1].strip('"')
            link_data[name] = link
    return link_data


def get_token(session, user, passwd, otp, session_id=None):
    '''
    Get an access token using 2FA
    '''
    if session_id is None:
        session_id = time.time()
    headers = {
        'content-type': 'application/json',
        'x-github-otp': otp,
    }
    resp = session.post(
        'https://api.github.com/authorizations',
        headers=headers,
        json={'scopes': ['public_repo'], 'note': 'test-{}'.format(time.time())},
        auth=requests.auth.HTTPBasicAuth(user, passwd),
    )
    if resp.status_code != 201:
        raise Exception(f"Bad reqonse {resp.status_code}")
    return resp.json()['token']


def parse_date(date_string):
    '''
    Parse a date returned by the GitHub API
    '''
    return datetime.datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%SZ")


def review_key(node):
    '''
    Return a sortable key for a pull request review
    '''
    return parse_date(node['submitted_at'])


def status_key(node):
    '''
    Return a sortable key for a pull request status
    '''
    return parse_date(node['created_at'])


def approvals(data, session):
    '''
    Get a list of current approvals for a pull request
    '''
    req_rev = []
    for reviewer in data['requested_reviewers']:
        req_rev.append(reviewer['id'])
    #print_pr(data, session)
    pr_url = data['_links']['self']['href']
    resp = session.get(f"{pr_url}/reviews")
    if resp.status_code != 200:
        raise Exception(f"Bad satatus code: {resp.status_code}")
    data = resp.json()
    seen_users = set()
    approvals = []
    for a in sorted(data, key=review_key, reverse=True):
        if a['user']['id'] in req_rev:
            continue
        if a['user']['id'] in seen_users:
            continue
        if a['state'] == 'APPROVED':
            approvals.append(a)
        seen_users.add(a['user']['id'])
    return approvals


def black_pr(pull_id, session):
    '''
    Run black against a PR and push the changes to the PR branch
    '''
    pull_url = f'https://api.github.com/repos/SaltStack/salt/pulls/{pull_id}'
    resp = session.get(pull_url)
    data = resp.json()
    if 'maintainer_can_modify' not in data or data['maintainer_can_modify'] is False:
        print("PR can not be modified")
    subprocess.run(f"git fetch origin pull/{pull_id}/head:pr/{pull_id}".split(), cwd='salt/')
    subprocess.run(f"git checkout pr/{pull_id}".split(), cwd='salt/')
    should_push = False

    subprocess.run(
        "isort $(git --no-pager diff --name-only FETCH_HEAD $(git merge-base FETCH_HEAD master))",
        shell=True,
        cwd='salt/',
        env=os.environ.copy(),
    )
    p = subprocess.run(
        ["git", "status"],
        cwd='salt/',
        stdout=subprocess.PIPE,
    )
    if p.stdout.splitlines()[-1] == b'nothing to commit, working tree clean':
        print("No changes from isort")
    else:
        subprocess.run(["git", "add", "."], cwd='salt/')
        subprocess.run(["git", "commit", "-S", "-m", "Isort changed files"], cwd='salt/')
        should_push = True

    subprocess.run(
        "black $(git --no-pager diff --name-only FETCH_HEAD $(git merge-base FETCH_HEAD master))",
        shell=True,
        cwd='salt/',
        env=os.environ.copy(),
    )
    p = subprocess.run(
        ["git", "status"],
        cwd='salt/',
        stdout=subprocess.PIPE,
    )
    if p.stdout.splitlines()[-1] == b'nothing to commit, working tree clean':
        print("No changes from black")
    else:
        subprocess.run(["git", "add", "."], cwd='salt/')
        subprocess.run(["git", "commit", "-S", "-m", "Blacken changed files"], cwd='salt/')
        should_push = True

    if should_push:
        fullname = data['head']['repo']['full_name']
        ref = data['head']['ref']
        subprocess.run(f"git push -f git@github.com:{fullname}.git pr/{pull_id}:{ref}".split(), cwd='salt/')
