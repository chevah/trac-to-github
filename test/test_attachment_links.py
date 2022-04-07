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

    def test_get_path_no_extension(self):
        """
        Generates the path for files without an extension.
        """
        self.assertEqual(
            get_attachment_path('/prefix', 5067, 'patch'),

            '/prefix/ticket/06d/06dd5be6fbd8d391bd906e39cff1ad2c2fb1e790/'
            'd75b3b528276d7a9f30a04b8bccaf74e1d61f67a'
            )
        self.assertEqual(
            get_attachment_path('/prefix', 569, '[issue563] read it immediately'),

            '/prefix/ticket/fc8/fc8d9e6e58db7ca861d6096d684bd0169ffd01cf/'
            'd1e7789f02d66b7ca7bd106e6fbc5ff950027d51'
            )