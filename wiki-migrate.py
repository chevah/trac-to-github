# Script to migrate the wiki to a repo.
import os
import sqlite3
import subprocess
import sys

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
            name, version, time, author, ipnr, text, comment, ro = row
            if author == 'trac':
                continue

            name = get_page_name(name)

            print("Adding", name)

            create_dirs(name)
            text = convert_content(text)
            write_file(name, text)
            commit_change(name, author, comment)


    finally:
        os.chdir(start_dir)


def get_page_name(name):
    """
    Return the full GitHub page file name.

    Adm/AllHand/Past -> Adm/AllHand/'Adm AllHand Past.rst'
    """
    name = PAGE_NAME_MAPPING.get(name, name)

    file_name = name.replace('/', ' ') + FILE_EXTENSION

    parts = name.split('/')[:-1]
    dir_name = ''

    if parts:
        dir_name = os.path.join(*parts)

    return os.path.join(dir_name, file_name)

def create_dirs(name):
    """
    Create the required directories for name.
    """

    parent = ''
    for part in name.split('/')[:-1]:
        parent = os.path.join(parent, part)
        if os.path.exists(parent):
            continue
        os.mkdir(parent)


def convert_content(text):
    """
    Conver from Trac wiki RST format to standard RST format.
    """
    # Remove RST wrapping.
    result = text.strip('}}}')
    result = result.strip('{{{')
    result = result.strip()
    result = result.strip('#!rst')
    result += '\n'

    return result


def write_file(name, text):
    """
    Write file content.
    """
    with open(name, 'w') as stream:
        stream.write(text)


def commit_change(path, author, comment):
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

    if DRY_RUN:
        print('Dry commit:', message, 'Git author:', git_author)
        return

    subprocess.run(['git', 'add', path])
    subprocess.run([
        'git', 'commit', '-a',
        '-m', message,
        '--author=' + git_author
        ])

if __name__ == '__main__':
    main()
