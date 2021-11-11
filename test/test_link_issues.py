import unittest

import config_test
import ticket_migrate_golden_comet_preview as tm

# Monkeypatch the SUT to use the test config.
tm.config = config_test


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
                component='client',
                priority='Low',
                keywords='tech-dept',
                status='',
                resolution='',
                ))

        self.assertEqual(
            ['priority-high'],
            tm.get_labels(
                component='client',
                priority='High',
                keywords='',
                status='',
                resolution='',
                ))

        # Handles "None" correctly.
        self.assertEqual(
            ['priority-low'],
            tm.get_labels(
                component='client',
                priority=None,
                keywords='',
                status=None,
                resolution=None,
                ))

    def test_get_labels_component_name(self):
        self.assertEqual(
            ['fallback', 'priority-low'],
            tm.get_labels('fallback', 'Low', '', '', ''))


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
            "trac-12345 bug was created by adiroiban on 1970-01-01 00:00:00Z.\n"
            "\n"
            "The ticket description.",

            tm.get_body(
                "The ticket description.",
                {
                    't_id': 12345,
                    't_type': 'bug',
                    'reporter': 'adi',
                    'time': 1234,
                    'changetime': 1234,
                    'branch': None,
                    },
                ticket_mapping={},
                )
            )

    def test_get_body_monospace(self):
        """
        Parses monospace squiggly brackets.
        """
        self.assertEqual(
            "trac-5432 task was created by someone_else on 1970-01-01 00:00:00Z.\n"
            "\n"
            "The ticket ```description```.",

            tm.get_body(
                "The ticket {{{description}}}.",
                {
                    't_id': 5432,
                    't_type': 'task',
                    'reporter': 'someone_else',
                    'time': 1234,
                    'changetime': 1234,
                    'branch': ''
                    },
                ticket_mapping={},
                )
            )


class TestParseBody(unittest.TestCase):
    def test_backticks(self):
        """
        Monospace backticks are preserved.
        """
        self.assertEqual(
            'text `monospace` text',
            tm.parse_body('text `monospace` text', ticket_mapping={})
            )

    def test_curly(self):
        self.assertEqual(
            'text ```monospace``` text',
            tm.parse_body('text {{{monospace}}} text', ticket_mapping={})
            )

    def test_monospace_escaping(self):
        """
        Escapes one monospace syntax with the other.
        """
        self.assertEqual(
            "```curly '''not bold'''```",
            tm.parse_body("{{{curly '''not bold'''}}}", ticket_mapping={})
            )

        self.assertEqual(
            "`backtick '''not bold'''`",
            tm.parse_body("`backtick '''not bold'''`", ticket_mapping={})
            )

        self.assertEqual(
            "quoting squigglies `{{{` or backticks ```````",
            tm.parse_body(
                "quoting squigglies `{{{` or backticks {{{`}}}",
                ticket_mapping={},
                )
            )

    def test_convert_content(self):
        """
        Headings are converted.
        """
        self.assertEqual(
            "# Some Top Heading\n"
            "\n"
            "Content ```here```",

            tm.parse_body(
                "= Some Top Heading =\n"
                "\n"
                "Content {{{here}}}",
                ticket_mapping={},
                )
            )

    def test_convert_content_in_monospace(self):
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
                "Some other content",
                ticket_mapping={},
                )
            )

    def test_convert_RST(self):
        """
        Leaves RST syntax as-is, does not treat it as monospace.
        """
        self.assertEqual(
            "\n"
            "\n"
            "Problem\n"
            "-------\n"
            "\n"
            "Solution.\n"
            "\n",

            tm.parse_body(
                "{{{\n"
                "#!rst\n"
                "\n"
                "Problem\n"
                "-------\n"
                "\n"
                "Solution.\n"
                "}}}\n",
                ticket_mapping={},
                )
            )

    def test_links(self):
        """
        TracWiki syntax links get converted to Markdown links.
        """
        self.assertEqual(
            "In order to "
            "[avoid third-party cookies](https://github.com/chevah/sftpplus.com/pull/254), "
            "we need to handle the contact form ourselves.",
            tm.parse_body(
                "In order to "
                "[https://github.com/chevah/sftpplus.com/pull/254 avoid third-party cookies], "
                "we need to handle the contact form ourselves.",
                ticket_mapping={},
                )
            )

    def test_ticket_replacement(self):
        """
        Converts Trac ticket IDs to GitHub numbers.
        """
        self.assertEqual(
            "Some issue is solved in [#234](some_url/234).",
            tm.parse_body(
                description="Some issue is solved in #123.",
                ticket_mapping={123: 'some_url/234'},
                )
            )

    def test_ticket_replacement_URL(self):
        """
        Converts Trac ticket URLs to GitHub URLs.
        """
        self.assertEqual(
            "Issue [#234](some_url/234).",
            tm.parse_body(
                description="Issue https://trac.chevah.com/ticket/123.",
                ticket_mapping={123: 'some_url/234'},
                )
            )

    def test_ticket_replacement_multiple(self):
        """
        Converts Trac ticket IDs to GitHub numbers.
        """
        self.assertEqual(
            "Some issue is solved in [#234](some_url/234).\n"
            "Another issue in the same ticket [#234](some_url/234).\n"
            "Yet another in a different ticket [#555](some_url/555).\n",
            tm.parse_body(
                description=(
                    "Some issue is solved in #123.\n"
                    "Another issue in the same ticket #123.\n"
                    "Yet another in a different ticket #444.\n"
                ),
                ticket_mapping={
                    123: 'some_url/234',
                    444: 'some_url/555'
                    },
                )
            )

    def test_ticket_replacement_URL_multiple(self):
        """
        Converts Trac ticket URLs to GitHub URLs.
        """
        self.assertEqual(
            "(but see [#234](some_url/234)).\n"
            "CMD [#234](some_url/234)",
            tm.parse_body(
                description="(but see https://trac.chevah.com/ticket/123).\n"
                            "CMD https://trac.chevah.com/ticket/123",
                ticket_mapping={123: 'some_url/234'},
                )
            )

    def test_missing_ticket_replacement(self):
        """
        Leaves missing Trac ticket IDs alone.
        """
        self.assertEqual(
            "Some issue is solved in #345.",
            tm.parse_body(
                description="Some issue is solved in #345.",
                ticket_mapping={123: 'some_url/234'},
                )
            )

    def test_no_ticket_replacement_in_preformatted(self):
        """
        Does not convert Trac ticket IDs to GitHub numbers
        in preformatted text.
        """
        self.assertEqual(
            "```Some issue is solved in #123.```",
            tm.parse_body(
                description="{{{Some issue is solved in #123.}}}",
                ticket_mapping={123: 'some_url/234'},
                )
            )

    def test_no_ticket_replacement_subset_match(self):
        """
        Does not convert Trac ticket IDs when only a string subset matches.
        """
        self.assertEqual(
            "Some issue is solved in #1234.",
            tm.parse_body(
                description="Some issue is solved in #1234.",
                ticket_mapping={123: 'some_url/234'},
                )
            )


class TestCommentGeneration(unittest.TestCase):
    def test_basic(self):
        """
        Check that the body of a comment includes its author and latest text.
        """
        trac_data = {
            'ticket': 3928,
            'c_time': 1489439926524055,
            'author': 'adi',
            'newvalue': 'Thanks.',
            }
        desired_body = (
            "Comment by adiroiban at 2017-03-13 21:18:46Z.\n"
            "\n"
            "Thanks."
            )

        self.assertEqual(
            desired_body,
            tm.GitHubRequest.commentFromTracData(
                trac_data,
                ticket_mapping={}
                )['body']
            )

    def test_no_user(self):
        """
        A user not defined in config.py is preserved.
        """
        trac_data = {
            'ticket': 3928,
            'c_time': 1488909819877801,
            'author': 'andradaE',
            'newvalue': 'Thanks.',
            }
        desired_body = (
            "Comment by andradaE at 2017-03-07 18:03:39Z.\n"
            "\n"
            "Thanks."
            )

        self.assertEqual(
            desired_body,
            tm.GitHubRequest.commentFromTracData(
                trac_data,
                ticket_mapping={}
                )['body']
            )

    def test_formatting(self):
        """
        Check that at least some formatting works.
        """
        trac_data = {
            'ticket': 3928,
            'c_time': 1488909819877801,
            'author': 'andradaE',
            'newvalue': (
                '[http://styleguide.chevah.com/tickets.html Style Guide]'
                )
            }
        desired_body = (
            "Comment by andradaE at 2017-03-07 18:03:39Z.\n"
            "\n"
            "[Style Guide](http://styleguide.chevah.com/tickets.html)"
            )

        self.assertEqual(
            desired_body,
            tm.GitHubRequest.commentFromTracData(
                trac_data,
                ticket_mapping={},
                )['body']
            )


class TestGitHubRequest(unittest.TestCase):
    """
    `GitHubRequest` objects are created from Trac data.
    """
    def test_fromTracDataMultiple(self):
        """
        A list of one dictionary with Trac ticket data results in
        one GitHubRequest object with the proper fields.
        """

        request_gen = tm.GitHubRequest.fromTracDataMultiple(
            trac_data=[{
                'component': 'trac-migration-staging',
                'owner': 'danuker',
                'status': 'closed',
                'resolution': 'wontfix',
                'milestone': 'some-milestone',
                'summary': 'summary',
                'description': 'description',
                'priority': 'high',
                'keywords': 'feature, easy',
                'reporter': 'adi',
                't_id': 6,
                't_type': 'task',
                'time': 1288883091000000,
                'changetime': 1360238496689890,
                'branch': 'https://github.com/chevah/agent-1.5/pull/10'
                }],
            ticket_mapping={},
            )

        requests = list(request_gen)
        self.assertEqual(1, len(requests))
        request = requests[0]

        self.assertEqual('trac-migration-staging', request.repo)
        self.assertEqual('chevah', request.owner)
        self.assertEqual('danuker', request.data['assignee'])
        self.assertEqual(
            ['easy', 'feature', 'priority-high', 'wontfix'],
            request.data['labels'])
        self.assertEqual('danuker', request.data['assignee'])
        self.assertEqual('some-milestone', request.milestone)
        self.assertEqual('summary', request.data['title'])
        self.assertEqual(
            'trac-6 task was created by adiroiban on 2010-11-04 15:04:51Z.\n'
            'Last changed on 2013-02-07 12:01:36Z.\n'
            'PR at https://github.com/chevah/agent-1.5/pull/10.\n'
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
            'server': 0,
            'client': 0,
            'commons': 0,
            'trac-migration-staging': 0,
            }

    def test_requestNextNumber_cached(self):
        """
        When the `next_numbers` cache has an entry for the repository,
        it returns the value of the entry.
        """
        self.sut.next_numbers['trac-migration-staging'] = 1234

        self.assertEqual(
            1234, self.sut.requestNextNumber('trac-migration-staging', []))

    def test_getMaxCreatedTicketNumber_match(self):
        """
        Returns the largest ticket number in the matching repository.
        """
        tickets = [
            'https://github.com/chevah/matching/issues/1',
            'https://github.com/chevah/matching/issues/2',
            'https://github.com/matching/nonmatching/issues/3'
            'https://github.com/matching/nonmatching/issues/4'
            ]

        self.assertEqual(
            2,
            self.sut.getMaxCreatedTicketNumber(
                repo='matching', ticket_urls=tickets)
            )

    def test_getMaxCreatedTicketNumber_nomatch(self):
        """
        The max created ticket is 0 when there are no matches.
        """
        tickets = [
            'https://github.com/chevah/nonmatching1/issues/1',
            'https://github.com/chevah/nonmatching2/issues/2'
            ]

        self.assertEqual(
            0,
            self.sut.getMaxCreatedTicketNumber(
                repo='matching', ticket_urls=tickets)
            )

    @staticmethod
    def generateTickets(numbers):
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

        self.assertEqual(
            (tickets, [1, 2, 3]),
            self.sut.orderTickets(tickets, [])
            )

    def test_orderTickets_skip(self):
        """
        Skip the tickets with a Trac ID lower than the next GitHub number,
        and start with the first ticket matching Trac ID and GitHub number.
        After the matching tickets are enumerated, continue with the others.
        """
        self.sut.next_numbers['trac-migration-staging'] = 4
        tickets = self.generateTickets([1, 2, 3, 4, 5, 6])

        self.assertEqual(
            (
                self.generateTickets([4, 5, 6, 1, 2, 3]),
                [4, 5, 6, 7, 8, 9],
                ),
            self.sut.orderTickets(tickets, [])
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
            (
                self.generateTickets([17, 16, 15]),
                [4, 5, 6],
                ),
            self.sut.orderTickets(tickets, [])
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
            (self.generateTickets([7, 5, 6]), [4, 5, 6]),
            self.sut.orderTickets(tickets, [])
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
            (
                self.generateTickets([2, 8, 4, 10, 6]),
                [7, 8, 9, 10, 11],
                ),
            self.sut.orderTickets(tickets, [])
            )

    def test_orderTickets_multiple_repos(self):
        """
        Splits tickets correctly across repositories.
        """
        self.sut.next_numbers['commons'] = 7
        self.sut.next_numbers['trac-migration-staging'] = 17
        tickets = [
            {'t_id': 1, 'component': 'commons'},
            {'t_id': 7, 'component': 'commons'},
            {'t_id': 11, 'component': 'trac-migration-staging'},
            {'t_id': 17, 'component': 'trac-migration-staging'},
            ]

        output, expected_github = self.sut.orderTickets(tickets, [])

        commons_output = [t for t in output if t['component'] == 'commons']
        migration_output = [
            t for t in output if t['component'] == 'trac-migration-staging']

        self.assertEqual(
            [
                {'t_id': 7, 'component': 'commons'},
                {'t_id': 1, 'component': 'commons'},
                ],
            commons_output
            )
        self.assertEqual(
            [
                {'t_id': 17, 'component': 'trac-migration-staging'},
                {'t_id': 11, 'component': 'trac-migration-staging'},
                ],
            migration_output
            )
        self.assertEqual(
            expected_github,
            [7, 8, 17, 18]
            )


if __name__ == '__main__':
    unittest.main()
