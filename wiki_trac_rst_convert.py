# Convert local files formated in Trac Wiki RST to GitHub RST.
import re
import sys
import os


def main():
    """
    Do the job.
    """
    if len(sys.argv) != 2:
        print("Need to pass the path to wiki base directory.")
        sys.exit(1)

    for root, _, files in os.walk(sys.argv[1]):
        for name in files:
            convert_file(os.path.join(root, name))

    print('Conversion complete.')


def convert_file(path: str):
    """
    In-place conversion of files; no backup.
    """
    if '.git' not in path:
        print('Converting ', path)
        with open(path) as f:
            text = f.read()

        with open(path, 'w') as f:
            f.write(convert_content(text))


def convert_content(text: str):
    """
    Convert from Trac wiki RST format to GitHub RST format.

    * Remove RST wrapping
    * Convert Trac wiki directives to GitHub wiki links.
    """

    to_remove = ['{{{', '#!rst', '}}}']
    for seq in to_remove:
        text = text.replace(seq, '')
    text = text.strip() + '\n'
    text = _trac_rst_wiki_to_github_links(text)

    return text


def _trac_rst_wiki_to_github_links(text: str):
    """
    Takes RST content with Trac wiki link directives
    and coverts the directives to inline GitHub wiki links.
    """

    link_matchers =[re.compile(r) for r in [
        ':trac:`wiki:(.+?)`',
        '`wiki:(.+?)`:trac:'
    ]]

    for link_re in link_matchers:
        wiki_titles = re.findall(link_re, text)
        for title in wiki_titles:
            text = re.sub(
                link_re,
                rf'`\1 <{_wiki_url(title)}>`__',
                text,
                1
            )

    return text


def _wiki_url(title):
    """
    GitHub Wiki collapses directory structure.

    After `wiki_migrate.py` replaced the path separator `/` with space,
    GitHub converts spaces to dashes in the URLs.

    Therefore, the original Trac links must get dashes as well.
    """

    return title.replace('/', '-')


if __name__ == '__main__':
    main()
