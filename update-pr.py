import os
import sys
import requests
import pprint
import logging
import subprocess
import lib


log = logging.getLogger(__name__)

jenkins_uri = os.environ.get('JENKINS_URI', 'https://jenkinsci.saltstack.com/api/json')
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
        if 'maintainer_can_modify' not in data or data['maintainer_can_modify'] is False:
            print("PR can not be modified")
        pprint.pprint(data)
        subprocess.run(f"git fetch origin pull/{pull_id}/head:pr/{pull_id}".split(), cwd='salt/')
        subprocess.run(f"git checkout pr/{pull_id}".split(), cwd='salt/')
        print("*-_-* Starting shell, make changes and exit. *-_-*")
        subprocess.run("bash", cwd='salt/', shell=True, env=os.environ.copy())
        answer = input('Push changes?')
        if answer.lower().strip() == 'y':
            fullname = data['head']['repo']['full_name']
            ref = data['head']['ref']
            print(f"git push -f git@github.com:{fullname}.git pr/{pull_id}:{ref}")
            subprocess.run(f"git push -f git@github.com:{fullname}.git pr/{pull_id}:{ref}".split(), cwd='salt/')




if __name__ == '__main__':
    main()

