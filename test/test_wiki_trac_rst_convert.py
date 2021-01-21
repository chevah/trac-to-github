import unittest

from wiki_trac_rst_convert import convert_content


class TracRstToVanillaRst(unittest.TestCase):
    """
    Test conversion of content from Trac-flavored reStructuredText to
    vanilla reStructuredText, that is supported by GitHub
    """

    def test_empty_adds_newline(self):
        """Adds a newline at the end of an empty file"""
        self.assertEqual(convert_content(''), '\n')

    def test_removes_RST_wrapping(self):
        """Removes the Trac RST markers"""
        self.assertEquals(
            convert_content('{{{#!rst}}}'),
            '\n'
        )
        self.assertEquals(
            convert_content('{{{\n#!rst\n}}}'),
            '\n'
        )

    def test_does_not_strip_content(self):
        """When using str.strip, it deletes too much. Prevent this."""
        self.assertEquals(
            convert_content('{{{\n#!rst\nsome content}}}'),
            '\nsome content\n'
        )

    def test_trac_wiki_link(self):
        """Converts a Trac wiki link to a plain link"""

        self.assertEquals(
            convert_content(':trac:`wiki:Requirements`\n'),
            '`Requirements`_\n'
            '.. _Requirements: Requirements.rst\n'
        )

    def test_trac_wiki_link_to_page_in_subdir(self):
        """Converts a Trac wiki link to a page in a subdirectory"""

        self.assertEquals(
            convert_content(':trac:`wiki:General/FreeSoftwareUsage`'),
            '`General/FreeSoftwareUsage`_\n'
            '.. _General/FreeSoftwareUsage: General/General FreeSoftwareUsage.rst\n'
        )

    # TODO: test links in directories above/sideways of current file
    # from Development/Development Environment.rst, we have a link
    # to :trac:`wiki:Infrastructure/OS/Windows`.
    # This must be translated as `../Infrastructure/OS/Infrastructure OS Windows.rst`?

    # Questions:
    # - How to test on files? bash?
    # - test just convert_file?
    # - Are these scripts used anywhere automated? I had to rename them.


if __name__ == '__main__':
    unittest.main()
