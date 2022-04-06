import unittest
from attachment_links import trac_hash, get_attachment_path


class TestTracToFilename(unittest.TestCase):
    def test_sha1_hash_ticket(self):
        """
        A ticket ID can be passed as string or integer,
        and the string representation will be used for the Trac hash.
        """
        self.assertEqual(
            trac_hash(5723),
            'de16c30ee166641da366bb04e3d0d53e0629adf6'
            )
        self.assertEqual(
            trac_hash('5723'),
            'de16c30ee166641da366bb04e3d0d53e0629adf6'
            )

    def test_sha1_hash_fname(self):
        """A file name is hashed the same as Trac."""
        self.assertEqual(
            trac_hash('patch-for-5723.patch'),
            'd1f782bc26dd1d35bbb3bfe4be40cf7c2e27a781'
            )

    def test_get_path(self):
        """
        Match the Trac attachment paths.

        Join with slashes the following:
        - ticket ID hash prefix,
        - ticket ID hash, and
        - filename hash.
        """
        self.assertEqual(
            get_attachment_path('/prefix/', 5723, 'patch-for-5723.patch'),

            '/prefix/ticket/de1/de16c30ee166641da366bb04e3d0d53e0629adf6/'
            'd1f782bc26dd1d35bbb3bfe4be40cf7c2e27a781.patch'
            )

    def test_get_path_no_slash_in_root(self):
        """
        Adds a slash at the end of the root when it is missing.
        """
        self.assertEqual(
            get_attachment_path('/prefix', 5723, 'patch-for-5723.patch'),

            '/prefix/ticket/de1/de16c30ee166641da366bb04e3d0d53e0629adf6/'
            'd1f782bc26dd1d35bbb3bfe4be40cf7c2e27a781.patch'
            )
