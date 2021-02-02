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
    if _is_rst_file(path):
        print('Converting ', path)
        with open(path) as f:
            text = f.read()

        with open(path, 'w') as f:
            f.write(convert_content(text))


def _is_rst_file(path: str):
    """
    Returns `True` if path looks like a ReStructuredText file.
    """
    path = path.lower()
    return path.endswith('rst') or path.endswith('rest')


def convert_content(text: str):
    """
    Convert from Trac wiki RST format to GitHub RST format.

    * Remove RST wrapping
    * Convert Trac wiki directives to GitHub wiki links.
    * Convert TracWiki headings, subheadings, and lists to RST.
    """

    to_remove = ['{{{', '#!rst', '}}}']
    for seq in to_remove:
        text = text.replace(seq, '')
    text = _remove_pageoutline(text)
    text = _remove_rst_contents(text)
    text = text.strip() + '\n'
    text = _ensure_rst_content_directive(text)
    text = _trac_to_github_wiki_links(text)
    text = _tracwiki_to_rst_links(text)
    text = _tracwiki_wiki_link_with_text_to_github_links(text)
    text = _trac_ticket_links(text)
    text = _tracwiki_heading_to_rst_heading(text)
    text = _tracwiki_subheading_to_rst_subheading(text)
    text = _tracwiki_list_dedent(text)
    text = _tracwiki_list_separate_from_paragraph(text)

    return text


def _remove_pageoutline(text: str):
    """
    Remove any TracWiki PageOutline directives
    """
    return text.replace('[[PageOutline]]', '')


def _remove_rst_contents(text: str):
    """
    Remove any RST `contents` directives
    """
    directive = r'\.\.(\ +)contents::\n'
    return re.sub(directive, '', text)


def _ensure_rst_content_directive(text: str):
    """
    Ensures a `contents` directive at the top of every document.
    """
    return (
        '.. contents::\n'
        '\n' +
        text
    )


def _trac_to_github_wiki_links(text: str):
    """
    Takes content with Trac wiki link directives and coverts
    the directives to inline GitHub wiki links.
    """

    link_matchers = [
        # RST markup:
        ':trac:`wiki:(.+?)`',
        '`wiki:(.+?)`:trac:',

        # TracWiki markup:
        r'`\[wiki:"?([^ ]+?)"?]`:trac:',
        r'\[wiki:"?([^ ]+?)"?]',
    ]

    for link_re in link_matchers:
        for title in _matches(link_re, text):
            text = _sub(link_re, f'`<{_wiki_url(title)}>`_', text)

    return text


def _tracwiki_to_rst_links(text: str):
    """
    Takes TracWiki markup and converts its links to RST links.
    """

    url = '[a-z]+://[^ ]+'
    link_text = '[^]]+'
    link_re = rf'\[({url}) ({link_text})]'

    for url, link_text in _matches(link_re, text):
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

    link_matchers = [
        rf'`\[wiki:({title}) ({link_text})]`:trac:',
        rf'\[wiki:({title}) ({link_text})]',
    ]

    for link_re in link_matchers:
        for title, link_text in _matches(link_re, text):
            if title == link_text:
                text = _sub(link_re, f'`<{_wiki_url(title)}>`_', text)
            else:
                replacement = f'`{link_text} <{_wiki_url(title)}>`_'
                text = _sub(link_re, replacement, text)

    return text


def _trac_ticket_links(text: str):
    """
    Replace Trac reference to ticket with an RST link to the ticket.
    """

    ticket_re = ':trac:`#([0-9]+)`'
    for ticket in _matches(ticket_re, text):
        text = _sub(
            ticket_re,
            f'`Trac #{ticket} <{TRAC_TICKET_PREFIX}{ticket}>`_',
            text
        )
    return text


def _tracwiki_heading_to_rst_heading(text: str):
    """
    Convert TracWiki 1st level headings to RST heading.

    TracWiki:

        = Some Top Heading =
        Content here

    RST conversion:

        Some Top Heading
        ================

        Content here
    """
    heading_re = '^= (.*) =$'
    for match in _matches(heading_re, text):
        text = _sub(heading_re, _underline(match, '='), text)

    return text


def _tracwiki_subheading_to_rst_subheading(text: str):
    """
    Convert TracWiki 2nd level headings to RST heading.

    TracWiki:

        == Some 2nd Heading ==
        Content here

    RST conversion:

        Some 2nd Heading
        ----------------
        Content here
    """
    heading_re = '^== (.*) ==$'
    for match in _matches(heading_re, text):
        text = _sub(heading_re, _underline(match, '-'), text)

    return text


def _tracwiki_list_dedent(text: str):
    """
    Remove a space before a list item, if exactly one space is
    before the asterisk.
    """

    indented_list_item_re = r'^ \* '
    for _ in _matches(indented_list_item_re, text):
        text = _sub(indented_list_item_re, '* ', text)

    return text


def _tracwiki_list_separate_from_paragraph(text: str):
    """
    During conversion from TracWiki to RST, ensure an empty line
    between each non-list-item and the list item following it, if any.
    """

    lines = text.split('\n')
    newlines = []
    was_list_item_or_blank = True

    for l in lines:
        is_list_item = re.match(r'^ *\* .*', l)
        if is_list_item:
            if not was_list_item_or_blank:
                newlines.append('')
            was_list_item_or_blank = True
        else:
            is_empty = l.strip() == ''
            was_list_item_or_blank = is_empty
        newlines.append(l)

    return '\n'.join(newlines)


def _underline(text: str, line_symbol: str):
    """
    Add a line made of `line_symbol` after given `text`,
    and return new text.
    """
    return text + "\n" + line_symbol * len(text)


def _matches(pattern: str, text: str):
    """
    Return all matches of a particular `pattern` occurring in `text`.
    """
    return re.findall(pattern, text, flags=re.MULTILINE)


def _sub(regex: str, replacement: str, text: str):
    """
    Substitute one occurrence of `regex` in `text` with `replacement`.
    Return the resulting new text.
    """
    return re.sub(regex, replacement, text, count=1, flags=re.MULTILINE)


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
