# Convert local files formated in Trac Wiki RST to Vanilla RST.
import re
import sys
import os

from wiki_migrate import get_page_name


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


def convert_file(path):
    """
    In-place conversion of files; no backup.
    """
    print('Converting ', path)
    with open(path) as f:
        text = f.read()

    with open(path, 'w') as f:
        f.write(convert_content(text))


def convert_content(text):
    """
    Conver from Trac wiki RST format to standard RST format.
    """
    # Remove RST wrapping.
    result = text.strip('}}}')
    result = result.strip('{{{')
    result = result.strip()
    result = result.replace('#!rst', '')
    result += '\n'
    result = _trac_wiki_to_plain_links(result)

    return result


def _trac_wiki_to_plain_links(text: str):
    """
    Converts Trac wiki links to plain relative links
    :param result:
    :return:
    """
    link_re = re.compile(':trac:`wiki:(.+)`')
    wiki_titles = re.findall(link_re, text)
    text = re.sub(link_re, r'`\1`_', text)

    return text + _wiki_footnotes(wiki_titles)


def _wiki_footnotes(wiki_titles):
    lines = [
        f'.. _{title}: {get_page_name(title)}\n'
        for title in wiki_titles
    ]

    return ''.join(lines)


if __name__ == '__main__':
    main()
