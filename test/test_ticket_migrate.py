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

        # Handles None correctly.
        self.assertEqual(
            set(),
            tm.labels_from_keywords(None))

    def test_get_labels_none(self):
        """
        The issues that do not map to the fallback repository
        get no label based on the component.
        """
        self.assertEqual(
            ['priority-low', 'tech-debt'],
            tm.get_labels(
                component='client', priority='Low', keywords='tech-dept'))

        self.assertEqual(
            ['priority-high'],
            tm.get_labels(
                component='client', priority='High', keywords=''))

        # Handles "None" correctly.
        self.assertEqual(
            ['priority-low'],
            tm.get_labels(
                component='client', priority=None, keywords=''))

    def test_get_labels_component_name(self):
        self.assertEqual(
            ['fallback', 'priority-low'],
            tm.get_labels('fallback', 'Low', ''))


class TestAssigneeMapping(unittest.TestCase):
    """
    Trac Owners are mapped to GitHub assignees.
    """
    def test_user_mapping(self):
        self.assertEqual(['adiroiban'], tm.get_assignees('adi'))

    def test_unknown_user_mapping(self):
        self.assertEqual([], tm.get_assignees('john-doe'))


class TestBody(unittest.TestCase):
    """
    The GitHub issue body is made from the Trac description and other fields.
    """
    def test_get_body_details(self):
        """
        Writes Trac ticket details at the beginning of the description.
        """
        self.assertEqual(
            "T12345 bug was created by adiroiban.\n"
            "\n"
            "The ticket description.",

            tm.get_body(
                "The ticket description.",
                {'t_id': '12345', 't_type': 'bug', 'reporter': 'adi'}
                )
            )

    def test_get_body_monospace(self):
        """
        Parses monospace squiggly brackets.
        """
        self.assertEqual(
            "T5432 task was created by someone_else.\n"
            "\n"
            "The ticket ```description```.",

            tm.get_body(
                "The ticket {{{description}}}.",
                {'t_id': '5432', 't_type': 'task', 'reporter': 'someone_else'}
                )
            )

    def test_parse_body_backticks(self):
        self.assertEqual(
            'text `monospace` text',
            tm.parse_body('text `monospace` text')
            )

    def test_parse_body_squiggly(self):
        self.assertEqual(
            'text ```monospace``` text',
            tm.parse_body('text {{{monospace}}} text')
            )

    def test_parse_body_monospace_escaping(self):
        """
        Escapes one monospace syntax with the other.
        """
        self.assertEqual(
            "```squiggly '''not bold'''```",
            tm.parse_body("{{{squiggly '''not bold'''}}}")
            )

        self.assertEqual(
            "`backtick '''not bold'''`",
            tm.parse_body("`backtick '''not bold'''`")
            )

        self.assertEqual(
            "quoting squigglies `{{{` or backticks ```````",
            tm.parse_body("quoting squigglies `{{{` or backticks {{{`}}}")
            )

    def test_parse_body_convert_content(self):
        """
        At least some TracWiki syntax is converted.
        """
        self.assertEqual(
            "Some Top Heading\n"
            "================\n"
            "\n"
            "Content ```here```",

            tm.parse_body(
                "= Some Top Heading =\n"
                "\n"
                "Content {{{here}}}"
                )
            )

    def test_parse_body_convert_content_in_monospace(self):
        """
        Monospaced sections are not converted from TracWiki syntax.
        """
        self.assertEqual(
            "Some other content\n"
            "\n"
            "```\n"
            "= Some Top Heading =\n"
            "\n"
            "Content here```\n"
            "Some other content",

            tm.parse_body(
                "Some other content\n"
                "\n"
                "{{{\n"
                "= Some Top Heading =\n"
                "\n"
                "Content here}}}\n"
                "Some other content"
                )
            )


class TestTicketSelection(unittest.TestCase):
    """
    Selects all tickets except those with closed status.
    """
    def test_status_closed(self):
        """
        Closed tickets are filtered out.
        """
        closed = [{'status': 'closed'}]
        self.assertEqual(
            [], list(tm.select_open_trac_tickets(closed)))

    def test_status_open(self):
        """
        Non-closed tickets are kept.
        """
        non_closed = [
            {'status': 'new'},
            {'status': 'assigned'},
            {'status': 'in_work'},
            {'status': 'needs_changes'},
            {'status': 'needs_merge'},
            {'status': 'needs_review'},
            ]
        self.assertEqual(
            non_closed, list(tm.select_open_trac_tickets(non_closed)))


class TestGitHubRequest(unittest.TestCase):
    """
    `GitHubRequest` objects are created from Trac data.
    """
    def test_fromTracDataMultiple(self):
        """
        A list of one dictionary with Trac ticket data results in
        one GitHubRequest object with the proper fields.
        """

        request_gen = tm.GitHubRequest.fromTracDataMultiple([{
            'component': 'trac-migration-staging',
            'owner': 'danuker',
            'summary': 'summary',
            'description': 'description',
            'priority': 'high',
            'keywords': 'feature, easy',
            'reporter': 'adi',
            't_id': '321',
            't_type': 'task',
            }])

        requests = list(request_gen)
        self.assertEqual(1, len(requests))
        request = requests[0]

        self.assertEqual('trac-migration-staging', request.repo)
        self.assertEqual('chevah', request.owner)
        self.assertEqual(['danuker'], request.data['assignees'])
        self.assertEqual(
            ['easy', 'feature', 'priority-high'],
            request.data['labels'])
        self.assertEqual(['danuker'], request.data['assignees'])
        self.assertEqual('summary', request.data['title'])
        self.assertEqual(
            'T321 task was created by adiroiban.\n'
            '\n'
            'description',
            request.data['body'])


if __name__ == '__main__':
    unittest.main()
