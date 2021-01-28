import unittest

from wiki_trac_rst_convert import convert_content


class TracToGitHubRST(unittest.TestCase):
    """
    Test conversion of content from Trac-flavored reStructuredText and
    TracWiki markup, into reStructuredText that is supported by GitHub
    """

    def assertConvertedContent(self, expected: str, source: str):
        """
        Run the Trac RST `source` through the converter,
        and assert that the output equals `expected`.

        Also expects the content to end with a newline. The newline is
        added here for convenience and readability of test cases.
        """
        self.assertEqual(expected + '\n', convert_content(source))

    def test_empty(self):
        """
        An empty string is appended a blank line.

        A file not ending in a newline character is not POSIX compliant,
        and may result in complaints from programs, like `git diff`
        saying "No newline at end of file".
        https://stackoverflow.com/a/729795/235463
        """
        self.assertConvertedContent('', '')

    def test_newline(self):
        """
        A newline will not get appended another newline.
        """
        self.assertConvertedContent('', '\n')

    def test_removes_rst_wrapping(self):
        """
        The Trac wiki syntax requires reStructuredText to be wrapped in
        {{{ #!rst }}} markers.
        It removes the TracWiki RST armor markup from the output.
        """
        self.assertConvertedContent('', '{{{#!rst}}}')
        self.assertConvertedContent(
            '',
            '\n'
            '{{{\n'
            '#!rst'
            '\n'
            '}}}')

    def test_does_not_strip_content(self):
        """
        Both RST and non-RST content is preserved, after stripping the markers.
        """
        self.assertConvertedContent(
            'some RST content and some non-RST content',
            '{{{#!rst some RST content}}} and some non-RST content'
        )

    def test_trac_rst_wiki_link(self):
        """
        Converts a Trac RST :wiki: directive to a GitHub wiki link.
        """

        self.assertConvertedContent(
            '`<Requirements>`_',
            ':trac:`wiki:Requirements`'
        )

    def test_trac_rst_wiki_link_to_page_in_subdir(self):
        """
        Converts Trac RST :wiki: directives to pages in subdirectories
        into GitHub wiki pages, which always have a link at root-level.
        """

        self.assertConvertedContent(
            '`<General-FreeSoftwareUsage>`_',
            ':trac:`wiki:General/FreeSoftwareUsage`'
        )

    def test_trac_rst_wiki_reverse_link(self):
        """
        Trac RST wiki links that are "reversed", with the URL first and
        the `:trac:` marker last are also handled.
        """

        self.assertConvertedContent(
            '`<Infrastructure-Services-LAN#services>`_',
            '`wiki:Infrastructure/Services/LAN#services`:trac:'
        )

    def test_several_trac_wiki_rst_links_with_content(self):
        """
        Converts several Trac RST :wiki: directives with content around them.
        Preserves all content and links.
        """

        self.assertConvertedContent(
            '* `<Requirements>`_\n'
            '* Some content\n'
            '* `<General-FreeSoftwareUsage>`_'
            ' List of free software used by Chevah Project.',

            '* :trac:`wiki:Requirements`\n'
            '* Some content\n'
            '* :trac:`wiki:General/FreeSoftwareUsage`'
            ' List of free software used by Chevah Project.'
        )

    def test_tracwiki_general_link(self):
        """
        Process general links from TracWiki format to plain RST links
        """
        self.assertConvertedContent(
            '`Buildbot <https://chevah.com/buildbot/>`_',
            '[https://chevah.com/buildbot/ Buildbot]'
        )

    def test_tracwiki_wiki_link(self):
        """
        Process wiki links from TracWiki format to GitHub-compatible
        RST wiki links.

        There are various combinations of:
        * link text different from article name
        * link text the same as article name, and
        * no link text, only article name
        """
        self.assertConvertedContent(
            '`Project management and administration <Administrative>`_',
            '[wiki:Administrative Project management and administration]'
        )
        self.assertConvertedContent(
            '`<Administrative>`_',
            '[wiki:Administrative Administrative]'
        )
        self.assertConvertedContent(
            '`<Administrative>`_',
            '[wiki:"Administrative"]'
        )
        self.assertConvertedContent(
            '`<Administrative-AllHandMeeting-Past>`_',
            '[wiki:"Administrative/AllHandMeeting/Past"]'
        )
        self.assertConvertedContent(
            '`<Infrastructure-Services-FileServer>`_',
            '`[wiki:Infrastructure/Services/FileServer]`:trac:'
        )
        self.assertConvertedContent(
            '`Overton <Infrastructure-Machines-Overton>`_',
            '`[wiki:Infrastructure/Machines/Overton Overton]`:trac:'
        )

    def test_trac_ticket(self):
        """
        Trac ticket references are converted to a hyperlink.
        This use case requires `config.py` with the following setting:

        TRAC_TICKET_PREFIX = 'https://trac.chevah.com/ticket/'
        """
        self.assertConvertedContent(
            '`Trac #738 <https://trac.chevah.com/ticket/738>`_',
            ':trac:`#738`'
        )

    def test_heading(self):
        """
        Converts headings to RST, which have an equal-sign-underline.
        Also handles the multiline case.

        Headings in TracWiki have single equal signs around them.
        """
        self.assertConvertedContent(
            'Heading\n'
            '=======',

            '= Heading ='
        )
        self.assertConvertedContent(
            'Policy and Process\n'
            '==================\n'
            '\n'
            'Some text',

            '= Policy and Process =\n'
            '\n'
            'Some text'
        )

    def test_subheading(self):
        """
        Converts subheadings to RST, which have a dash-underline.
        Also handle the multiline case.

        Subheadings in TracWiki have double equal signs around them.
        """
        self.assertConvertedContent(
            'Subheading\n'
            '----------',

            '== Subheading =='
        )
        self.assertConvertedContent(
            'Subheading\n'
            '----------\n'
            '\n'
            'Some text',

            '== Subheading ==\n'
            '\n'
            'Some text'
        )

    def test_list_indented(self):
        """
        Un-indents list items that are indented by one space exactly.

        This is to avoid RST interpreting lists indented by one space
        as quotations; we want them as unquoted lists instead.
        """
        self.assertConvertedContent(
            "* item 1\n"
            "* item 2\n"
            "* item 3",

            " * item 1\n"
            " * item 2\n"
            " * item 3"
        )

    def test_list_after_paragraph(self):
        """
        Separates lists from paragraphs by one empty line.

        In RST, when lists follow a paragraph without an empty line
        inbetween, they fail to parse as lists.
        """
        self.assertConvertedContent(
            "Paragraph\n\n"
            "* item 1\n"
            "* item 2\n"
            "* item 3",

            "Paragraph\n"
            "* item 1\n"
            "* item 2\n"
            "* item 3"
        )

    def test_list_after_paragraph_idempotent(self):
        """
        Does not add another line when there is already a line between
        a list and the paragraph before it.
        """

        self.assertConvertedContent(
            "Paragraph\n\n"
            "* item 1\n"
            "* item 2\n"
            "* item 3",

            "Paragraph\n\n"
            "* item 1\n"
            "* item 2\n"
            "* item 3"
        )

    def test_bold_is_not_list(self):
        """
        Italic text markup is preserved as in the TracWiki format.
        """

        self.assertConvertedContent(
            "Paragraph\n"
            "*italic text*",

            "Paragraph\n"
            "*italic text*",
        )


if __name__ == '__main__':
    unittest.main()
