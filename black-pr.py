import os
import sys
import requests
import logging
import lib


log = logging.getLogger(__name__)
log_level = os.environ.get('LOG_LEVEL', 'INFO')
log.setLevel(log_level)

github_user = os.environ['GITHUB_USER']
github_password = os.environ['GITHUB_PASSWORD']
git_key = os.environ['GIT_KEY']


def main():
    session = lib.authenticated_session(
        github_user,
        github_password,
        lib.get_otp(git_key)
    )
    for pull_id in sys.argv[1:]:
        lib.black_pr(pull_id, session)


if __name__ == '__main__':
    main()

