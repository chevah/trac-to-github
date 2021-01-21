# Convert local files formated in Trac Wiki RST to Vanilla RST.
import re
import sys
import os

from urllib.parse import quote

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


def convert_file(path: str):
    """
    In-place conversion of files; no backup.
    """
    print('Converting ', path)
    with open(path) as f:
        text = f.read()

    with open(path, 'w') as f:
        f.write(convert_content(text))


def convert_content(text: str):
    """
    Convert from Trac wiki RST format to standard RST format.
    """
    # Remove RST wrapping.
    result = text.strip('}}}')
    result = result.strip('{{{')
    result = result.replace('#!rst', '')
    result = result.strip()
    result = _trac_rst_wiki_to_plain_links(result)

    return result


def _trac_rst_wiki_to_plain_links(text: str):
    """
    Takes RST content with Trac wiki link directives
    and coverts the directives to single-line RST vanilla links.
    """

    link_re = re.compile(':trac:`wiki:(.+)`')
    wiki_titles = re.findall(link_re, text)
    for title in wiki_titles:
        text = re.sub(
            link_re,
            rf'`\1 <{_wiki_url(title)}>`__',
            text
        )
        print(text)

    return text


def _wiki_url(title):
    return quote(get_page_name(title))


if __name__ == '__main__':
    main()
