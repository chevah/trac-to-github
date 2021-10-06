import unittest

import ticket_migrate as tm


class TestRepositoryMapping(unittest.TestCase):
    """
    Trac components map to the configured GitHub repositories.

    These tests depend on `config.py` having the contents
    from `config.py.sample`.
    """

    def test_get_repo(self):
        """
        Check that the issue is opened in the correct GitHub repository
        based on the Trac component.
        """
        self.assertEqual(tm.get_repo('client'), 'client')
        self.assertEqual(tm.get_repo('commons'), 'commons')
        self.assertEqual(tm.get_repo('fallback'), 'server')


class TestLabelMapping(unittest.TestCase):
    """
    Trac labels are parsed based on component, priority, and keywords_string.

    These tests depend on `config.py` having the contents
    from `config.py.sample`.
    """

    def test_labels_from_keywords(self):
        """
        Parse and clean the Trac keywords.
        """
        # Split by space.
        self.assertEqual(
            {'easy', 'tech-debt'},
            tm.labels_from_keywords('easy tech-debt'))

        # Remove commas.
        self.assertEqual({'tech-debt'}, tm.labels_from_keywords('tech-debt,'))
        self.assertEqual(
            {'tech-debt', 'feature'},
            tm.labels_from_keywords('tech-debt, feature'))

        # Fix typos.
        self.assertEqual(
            {'tech-debt', 'easy'},
            tm.labels_from_keywords('tech-dept easy'))
        self.assertEqual(
            {'tech-debt'},
            tm.labels_from_keywords('tech-deb'))

        # Discard unknown words to prevent tag explosion.
        self.assertEqual(
            set(),
            tm.labels_from_keywords('unknown-tag'))

        # Deduplicate.
        self.assertEqual(
            {'tech-debt'},
            tm.labels_from_keywords('tech-deb, tech-debt tech-dept'))

    def test_get_labels_none(self):
        """
        The issues that do not map to the fallback repository
        get no label based on the component.
        """
        self.assertEqual(
            {'priority-low', 'tech-debt'},
            tm.get_labels(
                component='client', priority='Low', keywords='tech-dept'))
        self.assertEqual(
            {'priority-high'},
            tm.get_labels(
                component='client', priority='High', keywords=''))

    def test_get_labels_component_name(self):
        self.assertEqual(
            {'priority-low', 'fallback'},
            tm.get_labels('fallback', 'Low', ''))


class TestAssigneeMapping(unittest.TestCase):
    """
    Trac Owners are mapped to GitHub assignees.
    """
    def test_user_mapping(self):
        self.assertEqual(['adiroiban'], tm.get_assignees('adi'))

    def test_unknown_user_mapping(self):
        self.assertEqual([], tm.get_assignees('john-doe'))


if __name__ == '__main__':
    unittest.main()
