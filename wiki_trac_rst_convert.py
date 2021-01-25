# Convert local files formated in Trac Wiki RST to GitHub RST.
import re
import sys
import os

from config import TRAC_TICKET_PREFIX


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
    text = _trac_to_github_wiki_links(text)
    text = _tracwiki_to_rst_links(text)
    text = _tracwiki_wiki_link_with_text_to_github_links(text)
    text = _trac_ticket_links(text)

    return text


def _trac_to_github_wiki_links(text: str):
    """
    Takes content with Trac wiki link directives and coverts
    the directives to inline GitHub wiki links.
    """

    link_matchers = [re.compile(r) for r in [
        # RST markup
        ':trac:`wiki:(.+?)`',
        '`wiki:(.+?)`:trac:',

        # TracWiki markup
        '`\[wiki:"?([^ ]+?)"?]`:trac:',
        '\[wiki:"?([^ ]+?)"?]',
    ]]

    for link_re in link_matchers:
        wiki_titles = re.findall(link_re, text)
        for title in wiki_titles:
            text = _sub(link_re, f'`<{_wiki_url(title)}>`_', text)

    return text


def _tracwiki_to_rst_links(text: str):
    """
    Takes TracWiki markup and converts its links to RST links.
    """

    url = '[a-z]+://[^ ]+'
    link_text = '[^]]+'
    link_re = re.compile(f'\[({url}) ({link_text})]')

    matches = re.findall(link_re, text)
    for url, link_text in matches:
        text = _sub(link_re, f'`{link_text} <{url}>`_', text)

    return text


def _tracwiki_wiki_link_with_text_to_github_links(text: str):
    """
    Takes TracWiki markup and converts its Wiki links which have
    explicit link text into RST links.
    If the link text is the same as the article name, generate a more
    compact syntax.
    """

    title = '[^ ]+'
    link_text = '[^]]+'

    link_matchers = [re.compile(r) for r in [
        f'`\[wiki:({title}) ({link_text})]`:trac:',
        f'\[wiki:({title}) ({link_text})]',
    ]]

    for link_re in link_matchers:
        matches = re.findall(link_re, text)
        for title, link_text in matches:
            if title == link_text:
                text = _sub(link_re, f'`<{_wiki_url(title)}>`_', text)
            else:
                replacement = f'`{link_text} <{_wiki_url(title)}>`_'
                text = _sub(link_re, replacement, text)

    return text


def _trac_ticket_links(text: str):
    """
    Replace Trac reference to ticket with actual link to the ticket
    """

    ticket_re = ':trac:`#([0-9]+)`'
    matches = re.findall(ticket_re, text)
    for ticket in matches:
        text = _sub(
            ticket_re,
            f'`Trac #{ticket} <{TRAC_TICKET_PREFIX}{ticket}>`_',
            text
        )
    return text


def _sub(link_re: str, replacement: str, text: str):
    """
    Substitute one occurrence of `link_re` in `text` with `replacement`.
    Return the resulting new text.
    """
    return re.sub(link_re, replacement, text, 1)


def _wiki_url(title: str):
    """
    GitHub Wiki collapses directory structure.

    After `wiki_migrate.py` replaced the path separator `/` with space,
    GitHub converts spaces to dashes in the URLs.

    Therefore, the original Trac links must get dashes as well.
    """

    return title.replace('/', '-')


if __name__ == '__main__':
    main()
