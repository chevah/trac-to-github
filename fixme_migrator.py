import os
import re
import sys

# The GitHub name of the project we're working on.
PROJECT_NAME = 'server'
FIXME_REGEX = re.compile(r'FIXME:(\d+):')


def should_skip_path(fpath):
    """
    Returns true if a path should be skipped instead of migrated.
    """
    if fpath.endswith('.pyc'):
        return True

    return any(substr in fpath for substr in [
        '.git',
        'node_modules',
        'python2.7',
        'nodeenv',
        f'build-{PROJECT_NAME}',
        'release-notes',
        ])


def replace_match(match, ticket_mapping):
    group = match.group(1)
    try:
        return f'FIXME:{ticket_mapping[group]}:'
    except KeyError:
        if group in ticket_mapping.values():
            print(f'Ticket ID may have been migrated: {group}')
        else:
            print(f'Ticket ID not in this project: {group}')
        return f'FIXME:{group}:'


def migrate(ticket_mapping, text):
    return FIXME_REGEX.sub(
        lambda match: replace_match(match, ticket_mapping),
        text
        )


def parse_tsv(project, tsv_text):
    """
    Parse content in TSV format with tickets created,
    and selects only the ones for the given project name.
    """
    old_to_new = re.compile(
        f'https://trac.chevah.com/ticket/(\\d+)\t'
        f'https://github.com/chevah/{project}/issues/(\\d+)\n'
        )

    return {
        match[0]: match[1]
        for match in re.findall(old_to_new, tsv_text)
        }


def main():
    """
    Perform FIXME in-place migration on a given directory.
    """
    args = sys.argv[1:]
    if len(args) != 1:
        raise ValueError('There should be exactly one argument: '
                         'the path to the root directory to update.\n'
                         f'Provided: {args}')

    with open('tickets_created.tsv') as tickets_f:
        tsv_text = tickets_f.read()
        mapping = parse_tsv(project=PROJECT_NAME, tsv_text=tsv_text)

        for root, dirs, fnames in os.walk(args[0]):
            for fname in fnames:
                fpath = os.path.join(root, fname)

                if should_skip_path(fpath):
                    continue

                try:
                    with open(fpath) as f:
                        source_code = f.read()
                        new_source = migrate(mapping, source_code)
                    if source_code != new_source:
                        with open(fpath, 'w') as f:
                            f.write(new_source)
                except UnicodeDecodeError:
                    # Likely a binary file. Skip it.
                    continue


if __name__ == '__main__':
    main()
