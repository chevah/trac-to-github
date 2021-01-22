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
        self.assertEqual(convert_content(source), expected)

    def test_empty(self):
        """Ensures that an empty string is returned unchanged."""
        self.assertConvertedContent('', '')

    def test_removes_rst_wrapping(self):
        """
        Removes the Trac RST markers, as well as the newlines around the
        RST content.

        The Trac wiki syntax requires reStructuredText to be wrapped in
        {{{ #!rst ... }}} blocks. Here, we make sure they don't appear
        in the output.
        """
        self.assertConvertedContent('', '{{{\n#!rst\n}}}')

    def test_does_not_strip_rst_content(self):
        """
        The RST content itself is preserved.
        """
        self.assertConvertedContent(
            'some content',
            '{{{#!rst some content}}}'
        )

    def test_trac_rst_wiki_link(self):
        """
        Converts a Trac RST :wiki: directive to an inline link.
        GitHub does not add `.rst` at the end of the URL.
        """

        self.assertConvertedContent(
            '`Requirements <Requirements>`__',
            ':trac:`wiki:Requirements`'
        )

    def test_trac_rst_wiki_link_to_page_in_subdir(self):
        """
        Converts Trac RST :wiki: directives to pages in subdirectories.

        - Spaces in the URL are converted to dashes by GitHub.
        - The subdirectory is not shown by GitHub, all pages appear
            at the same level.
        """

        self.assertConvertedContent(
            '`General/FreeSoftwareUsage <General-FreeSoftwareUsage>`__',
            ':trac:`wiki:General/FreeSoftwareUsage`'
        )

    def test_several_trac_wiki_rst_links_with_content(self):
        """
        Converts several Trac RST :wiki: directives with content around them.
        """

        self.assertConvertedContent(
            '* `Requirements <Requirements>`__\n'
            '* Some content\n'
            '* `General/FreeSoftwareUsage <General-FreeSoftwareUsage>`__'
            ' List of free software used by Chevah Project.',

            '* :trac:`wiki:Requirements`\n'
            '* Some content\n'
            '* :trac:`wiki:General/FreeSoftwareUsage`'
            ' List of free software used by Chevah Project.'
        )

    def test_several_links(self):
        """Converts several Trac RST links on the same line."""
        self.assertConvertedContent(
            '* `Requirements <Requirements>`__'
            '* `General/FreeSoftwareUsage <General-FreeSoftwareUsage>`__'
            '* `General/FreeSoftwareUsage <General-FreeSoftwareUsage>`__',

            '* :trac:`wiki:Requirements`'
            '* :trac:`wiki:General/FreeSoftwareUsage`'
            '* :trac:`wiki:General/FreeSoftwareUsage`'
        )


if __name__ == '__main__':
    unittest.main()
