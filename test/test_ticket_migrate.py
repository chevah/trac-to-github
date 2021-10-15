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


class TestParseBody(unittest.TestCase):
    def test_parse_body_backticks(self):
        """
        Monospace backticks are preserved.
        """
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
        Headings are converted.
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

    def test_parse_body_convert_RST(self):
        """
        Leaves RST syntax as-is, does not treat it as monospace.
        """
        self.assertEqual(
            "\n"
            "\n"
            "Problem\n"
            "-------\n"
            "\n"
            "The buildslaves have a builder which automatically updates the 'deps' repo on each slave.\n"
            "\n",

            tm.parse_body(
                "{{{\n"
                "#!rst\n"
                "\n"
                "Problem\n"
                "-------\n"
                "\n"
                "The buildslaves have a builder which automatically updates the 'deps' repo on each slave.\n"
                "}}}\n"
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
            [], list(tm.select_open_tickets(closed)))

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
            non_closed, list(tm.select_open_tickets(non_closed)))


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
            't_id': 321,
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


class TestNumberPredictor(unittest.TestCase):
    """
    NumberPredictor orders GitHub issues so they are created to match Trac ID,
    as much as possible.
    """
    def setUp(self):
        """
        Initialize the NumberPredictor, and the `next_numbers` cache.
        """

        self.sut = tm.NumberPredictor()

        # Break the cache of next_numbers to prevent accidental get requests.
        self.sut.next_numbers = {
            'server': 'not-a-number',
            'client': 'not-a-number',
            'commons': 'not-a-number',
            'trac-migration-staging': 'not-a-number',
            }

    def test_requestNextNumber_cached(self):
        """
        When the `next_numbers` cache has an entry for the repository,
        it returns the value of the entry.
        """
        self.sut.next_numbers['trac-migration-staging'] = 1234

        self.assertEqual(
            1234, self.sut.requestNextNumber('trac-migration-staging'))

    def generateTickets(self, numbers):
        """
        Create a list of tickets with given IDs.
        """
        return [
            {'t_id': number, 'component': 'trac-migration-staging'}
            for number in numbers
            ]

    def test_orderTickets_simple(self):
        """
        Return the tickets to submit in the same order,
        if the next GitHub number is 1.
        """
        tickets = self.generateTickets([1, 2, 3])
        self.sut.next_numbers['trac-migration-staging'] = 1

        self.assertEqual(tickets, self.sut.orderTickets(tickets))

    def test_orderTickets_skip(self):
        """
        Skip the tickets with a Trac ID lower than the next GitHub number,
        and start with the first ticket matching Trac ID and GitHub number.
        After the matching tickets are enumerated, continue with the others.
        """
        self.sut.next_numbers['trac-migration-staging'] = 4
        tickets = self.generateTickets([1, 2, 3, 4, 5, 6])

        self.assertEqual(
            self.generateTickets([4, 5, 6, 1, 2, 3]),
            self.sut.orderTickets(tickets)
            )

    def test_orderTickets_unfillable_gap(self):
        """
        When the minimum Trac ID is greater than the next GitHub number,
        and the gap can't be filled with newer Trac IDs,
        still return all the tickets.
        """
        self.sut.next_numbers['trac-migration-staging'] = 4
        tickets = self.generateTickets([15, 16, 17])

        self.assertEqual(
            self.generateTickets([17, 16, 15]),
            self.sut.orderTickets(tickets)
            )

    def test_orderTickets_gap_fillable_with_new(self):
        """
        When the minimum Trac ID is greater than the next GitHub number,
        the highest Trac IDs are sacrificed until they fill the gap,
        and after the gap is filled, the Trac IDs match.
        """
        self.sut.next_numbers['trac-migration-staging'] = 4
        tickets = self.generateTickets([5, 6, 7])

        self.assertEqual(
            self.generateTickets([7, 5, 6]),
            self.sut.orderTickets(tickets)
            )

    def test_orderTickets_gap_fillable_with_old(self):
        """
        When the minimum Trac ID is lower than the next GitHub number,
        fill any gaps with Trac IDs already taken by other GH numbers,
        In the example, Trac IDs 8 and 10 will match the GitHub IDs.
        """
        self.sut.next_numbers['trac-migration-staging'] = 7
        tickets = self.generateTickets([2, 4, 6, 8, 10])

        self.assertEqual(
            self.generateTickets([2, 8, 4, 10, 6]),
            self.sut.orderTickets(tickets)
            )


if __name__ == '__main__':
    unittest.main()
