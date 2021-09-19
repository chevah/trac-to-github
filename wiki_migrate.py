"""
Generate local wiki files based on Trac DB file.

* SQlite3 DB
* PSQL dump
"""
import os
import sqlite3
import subprocess
import sys
from datetime import datetime

from config import USER_MAPPING, DEFAULT_GITHUB_USER, FILE_EXTENSION

# Set to True to not commit.
DRY_RUN = False


# Wiki names to file names.
PAGE_NAME_MAPPING = {
    'WikiStart': 'Home',
}


def main(args):
    """
    Do the job.
    """

    if len(args) != 2:
        print("Need to pass the path to DB file and git repo as arguments.")
        sys.exit(1)

    db_file = args[0]
    target_repo = args[1]

    if db_file.endswith('.db3'):
        return _mirate_sqlite(db_file, target_repo)

    if db_file.endswith('.psql'):
        return _mirate_pq_dump(db_file, target_repo)


def _mirate_sqlite(db_file, target_repo):
    """
    Generate files based on SQLite3 db file.
    """
    db = sqlite3.connect(db_file)

    start_dir = os.getcwd()
    try:
        os.chdir(target_repo)

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


def _mirate_pq_dump(db_file, target_repo):
    """
    Generate files based on pg_dump file.

    pg_dump  --no-owner --data-only  --file=trac-wiki.dump --table=wiki trac
    """

    copy_started = False
    # The dump is not sorted by timestamp, so we need to manually sort it
    # and keep all pages in memory.
    changes = []

    with open(db_file, 'rb') as stream:
        while True:
            line = stream.readline()

            if not line:
                # End of stream.
                # Most likely this is not heat.
                break

            if line == b'\\.\n':
                # End of COPY dump.
                break

            if line.startswith(b'COPY '):
                # We can start to process the next line.
                copy_started = True
                continue

            if not copy_started:
                # We are still in the header
                continue


            line = line.decode('utf-8')

            name, version, timestamp, author, ipnr, rest = line.split('\t', 5)
            text, comment, ro = rest.rsplit('\t', 2)

            if author == 'trac':
                # This is internal trac update.
                continue

            timestamp = int(timestamp)
            name = get_page_name(name)

            text = text.replace('\\r\\n', '\r\n')
            text = text.replace('\\n', '\n')
            changes.append({
                'name': name,
                'timestamp': timestamp,
                'author': author,
                'text': text,
                'comment': comment,
                })

    start_dir = os.getcwd()
    try:
        os.chdir(target_repo)

        for change in sorted(changes, key=lambda k: k['timestamp']):

            print("Adding", change['name'])

            write_file(change['name'], change['text'])
            commit_change(
                change['name'],
                change['author'],
                change['comment'],
                change['timestamp'] / 1000000,
                )

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
    default_user = DEFAULT_GITHUB_USER
    if not default_user:
        # Create a default git user on the fly if no fix user is configured.
        default_user = (author, '{} <anonymous@example.com>'.format(author))

    git_user, git_author = USER_MAPPING.get(author, default_user)

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
    main(sys.argv[1:])
