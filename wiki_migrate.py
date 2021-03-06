# Script to migrate the wiki to a repo.
import os
import sqlite3
import subprocess
import sys
from datetime import datetime

from config import USER_MAPPING

# Set to True to not commit.
DRY_RUN = False

DEFAULT_GITHUB_USER = USER_MAPPING['adi']


# Wiki names to file names.
PAGE_NAME_MAPPING = {
    'WikiStart': 'Home',
}

FILE_EXTENSION = '.rst'

def main():
    """
    Do the job.
    """

    if len(sys.argv) != 3:
        print("Need to pass the path to Trac DB and git repo as arguments.")
        sys.exit(1)

    db = sqlite3.connect(sys.argv[1])

    start_dir = os.getcwd()
    try:
        os.chdir(sys.argv[2])

        for row in db.execute('SELECT * FROM wiki ORDER BY time'):
            name, version, timestamp, author, ipnr, text, comment, ro = row
            if author == 'trac':
                continue

            name = get_page_name(name)

            print("Adding", name)

            write_file(name, text)
            commit_change(name, author, comment, timestamp / 1000000)


    finally:
        os.chdir(start_dir)


def get_page_name(name):
    """
    Return the full GitHub page file name.

    Adm/AllHand/Past -> Adm/AllHand/'Adm AllHand Past.rst'
    """
    name = PAGE_NAME_MAPPING.get(name, name)

    return name.replace('/', ' ').strip() + FILE_EXTENSION


def write_file(name, text):
    """
    Write file content.
    """
    with open(name, 'w') as stream:
        stream.write(text)


def commit_change(path, author, comment, timestamp):
    """
    Commit the current file.
    """
    try:
        git_user, git_author = USER_MAPPING.get(author, DEFAULT_GITHUB_USER)
    except:
        import pdb; import sys; sys.stdout = sys.__stdout__; pdb.set_trace()

    name = path.rsplit(' ', 1)[-1]

    if comment:
        message = comment + ' ' +  name + ' modified by ' + git_user
    else:
        message = name + ' modified by ' + git_user

    git_date = datetime.fromtimestamp(timestamp).isoformat()

    if DRY_RUN:
        print(git_date + ': Dry commit:', message, 'Git author:', git_author)
        return

    subprocess.run(['git', 'add', path])
    subprocess.run([
        'git', 'commit', '-a',
        '-m', message,
        '--author=' + git_author,
        '--date=' + git_date,
        ])

if __name__ == '__main__':
    main()
