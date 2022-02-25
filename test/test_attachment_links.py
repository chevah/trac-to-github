import unittest
from attachment_links import trac_hash, get_path


class TestTracToFilename(unittest.TestCase):
    def test_sha1_hash_ticket(self):
        """A ticket ID can be hashed as string or integer."""
        self.assertEqual(
            trac_hash(5723),
            'de16c30ee166641da366bb04e3d0d53e0629adf6'
            )
        self.assertEqual(
            trac_hash('5723'),
            'de16c30ee166641da366bb04e3d0d53e0629adf6'
            )

    def test_sha1_hash_fname(self):
        """A file path can be hashed."""
        self.assertEqual(
            trac_hash('patch-for-5723.patch'),
            'd1f782bc26dd1d35bbb3bfe4be40cf7c2e27a781'
            )

    def test_get_path(self):
        """
        get_path matches the Trac attachment paths.

        Join the prefix of ticket ID hash, entire ticket ID hash,
        and filename hash with slashes.
        """
        self.assertEqual(
            get_path('/prefix/', 5723, 'patch-for-5723.patch'),

            '/prefix/de1/de16c30ee166641da366bb04e3d0d53e0629adf6/'
            'd1f782bc26dd1d35bbb3bfe4be40cf7c2e27a781'
            )

    def test_get_path_no_slash_in_prefix(self):
        """
        get_path adds a slash at the end of the prefix when it is missing.
        """
        self.assertEqual(
            get_path('/prefix', 5723, 'patch-for-5723.patch'),

            '/prefix/de1/de16c30ee166641da366bb04e3d0d53e0629adf6/'
            'd1f782bc26dd1d35bbb3bfe4be40cf7c2e27a781'
            )