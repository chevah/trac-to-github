import unittest
from fixme_migrator import migrate, parse_tsv


class TestMigration(unittest.TestCase):
    def test_migrate(self):
        """
        Replace old ticket IDs in a text with new ones from a mapping.
        Returns the new text.
        """

        old_to_new = {'1234': '1235'}
        text = """
            # FIXME:1234:
            Some other text here.
            """

        self.assertEqual(
            migrate(old_to_new, text),
            """
            # FIXME:1235:
            Some other text here.
            """)

    def test_migrate_overlap(self):
        """
        When a new ticket has the same ID as a different old one,
        the system migrates both correctly.
        """

        old_to_new = {'12': '34', '34': '12'}
        text = """
            # FIXME:12:
            # FIXME:34:
            """

        self.assertEqual(
            migrate(old_to_new, text),
            """
            # FIXME:34:
            # FIXME:12:
            """
            )

    def test_fixme_unknown(self):
        """
        Throws an error on an unknown FIXME.
        """
        old_to_new = {'1234': '1235'}
        text = """
            # FIXME:1235:
            Some other text here.
            """

        with self.assertRaises(ValueError) as error:
            migrate(old_to_new, text)
        self.assertEqual(
            str(error.exception),
            'Ticket ID not in this project: 1235'
            )


class TestProjectFilter(unittest.TestCase):
    def test_tsv_parse(self):
        """
        Parses a TSV into a dictionary of old ID -> new ID.
        """
        tsv_text = """
https://trac.chevah.com/ticket/2166	https://github.com/chevah/server/issues/2166
https://trac.chevah.com/ticket/1891	https://github.com/chevah/server/issues/5459
"""
        self.assertEqual(
            parse_tsv(project='server', tsv_text=tsv_text),
            {'2166': '2166', '1891': '5459'}
            )

    def test_project_filter(self):
        """
        Out of a TSV with tickets migrated to various projects,
        it only selects the current one for migration.
        """
        tsv_text = """
https://trac.chevah.com/ticket/2166	https://github.com/chevah/server/issues/2166
https://trac.chevah.com/ticket/10	https://github.com/chevah/sftpplus.com/issues/373
https://trac.chevah.com/ticket/1891	https://github.com/chevah/server/issues/5459
https://trac.chevah.com/ticket/5052	https://github.com/chevah/sftpplus.com/issues/387
"""
        self.assertEqual(
            parse_tsv(project='server', tsv_text=tsv_text),
            {'2166': '2166', '1891': '5459'}
            )


if __name__ == '__main__':
    unittest.main()
