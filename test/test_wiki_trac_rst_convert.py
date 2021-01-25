import unittest

from wiki_trac_rst_convert import convert_content


class TracRstToVanillaRst(unittest.TestCase):
    """
    Test conversion of content from Trac-flavored reStructuredText to
    vanilla reStructuredText, that is supported by GitHub
    """

    def assertConvertedContent(self, expected: str, source: str):
        """
        Run the Trac RST `source` through the converter,
        and assert that the output equals `expected`.
        """
        self.assertEqual(expected, convert_content(source))

    def test_empty(self):
        """
        An empty string is appended a blank line.

        A file not ending in a newline character is not POSIX compliant,
        and may result in complaints from programs, like `git diff`
        saying "\ No newline at end of file".
        https://stackoverflow.com/a/729795/235463
        """
        self.assertConvertedContent('\n', '')

    def test_newline(self):
        """
        A newline should not be appended another newline.
        """
        self.assertConvertedContent('\n', '\n')

    def test_removes_rst_wrapping(self):
        """
        The Trac wiki syntax requires reStructuredText to be wrapped in
        {{{ #!rst }}} markers.
        They must be removed from the output.
        """
        self.assertConvertedContent('\n', '{{{#!rst}}}')

    def test_does_not_strip_content(self):
        """
        Both RST and non-RST content is preserved, after stripping the markers.
        """
        self.assertConvertedContent(
            'some RST content and some non-RST content\n',
            '{{{#!rst some RST content}}} and some non-RST content'
        )

    def test_trac_rst_wiki_link(self):
        """
        Converts a Trac RST :wiki: directive to a GitHub wiki link.
        """

        self.assertConvertedContent(
            '`Requirements <Requirements>`__\n',
            ':trac:`wiki:Requirements`'
        )

    def test_trac_rst_wiki_link_to_page_in_subdir(self):
        """
        Converts Trac RST :wiki: directives to pages in subdirectories
        into GitHub wiki pages, which always have a link at root-level.
        """

        self.assertConvertedContent(
            '`General/FreeSoftwareUsage <General-FreeSoftwareUsage>`__\n',
            ':trac:`wiki:General/FreeSoftwareUsage`'
        )

    def test_trac_rst_wiki_reverse_link(self):
        """
        Some Trac RST wiki links are "reversed", with the URL first and
        the `:trac:` marker last. Handle them.
        """

        self.assertConvertedContent(
            '`Infrastructure/Services/LAN#services <Infrastructure-Services-LAN#services>`__\n',
            '`wiki:Infrastructure/Services/LAN#services`:trac:'
        )

    def test_several_trac_wiki_rst_links_with_content(self):
        """
        Converts several Trac RST :wiki: directives with content around them.
        Preserves all content and links.
        """

        self.assertConvertedContent(
            '* `Requirements <Requirements>`__\n'
            '* Some content\n'
            '* `General/FreeSoftwareUsage <General-FreeSoftwareUsage>`__'
            ' List of free software used by Chevah Project.\n',

            '* :trac:`wiki:Requirements`\n'
            '* Some content\n'
            '* :trac:`wiki:General/FreeSoftwareUsage`'
            ' List of free software used by Chevah Project.'
        )


if __name__ == '__main__':
    unittest.main()
