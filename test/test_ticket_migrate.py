import unittest

import config_test
import ticket_migrate_golden_comet_preview as tm

# Monkeypatch the SUT to use the test config.
tm.config = config_test


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
        # Split by space or comma.
        self.assertEqual(
            ['easy', 'tech-debt'],
            tm.labels_from_keywords('easy tech-debt'))
        self.assertEqual(
            ['easy', 'tech-debt'],
            tm.labels_from_keywords('easy,tech-debt'))

        # Remove commas.
        self.assertEqual(['tech-debt'], tm.labels_from_keywords('tech-debt,'))
        self.assertEqual(
            ['tech-debt', 'feature'],
            tm.labels_from_keywords('tech-debt, feature'))

        # Handles None correctly.
        self.assertEqual(
            [],
            tm.labels_from_keywords(None))

        # Handles empty tags correctly.
        self.assertEqual(
            [],
            tm.labels_from_keywords(''))
        self.assertEqual(
            [],
            tm.labels_from_keywords(', , ,,  '))
        self.assertEqual(
            ['priority-normal', 'tag'],
            tm.get_labels(keywords='tag, ,tag ,,tag  '))

    def test_get_labels_none(self):
        """
        When priority field is missing, it is automatically assigned "normal".
        """
        self.assertEqual(
            ['client', 'priority-low', 'tech-debt'],
            tm.get_labels(
                component='client',
                priority='Low',
                keywords='tech-debt',
                status='',
                resolution='',
                ))

        self.assertEqual(
            ['priority-high', 'server'],
            tm.get_labels(
                component='server',
                priority='High',
                keywords='',
                status='',
                resolution='',
                ))

        # Handles missing args (None) correctly.
        self.assertEqual(['priority-normal'], tm.get_labels())

    def test_get_labels_component_name(self):
        """
        The component gets converted to a label.
        """
        self.assertEqual(
            ['priority-low', 'release management'],
            tm.get_labels(
                component='release management',
                priority='Low'
                )
            )

    def test_labels_from_status_and_resolution(self):
        """
        Status can be empty/None or:
            new, assigned, closed, reopened.
        If status is closed, resolution can be empty/None or:
            duplicate, fixed, invalid,
        """
        self.assertEqual(
            {'assigned'},
            tm.labels_from_status_and_resolution('assigned', '')
            )
        self.assertEqual(
            {'assigned'},
            tm.labels_from_status_and_resolution('assigned', None)
            )
        self.assertEqual(
            {'closed'},
            tm.labels_from_status_and_resolution('closed', None)
            )
        self.assertEqual(
            {'worksforme'},
            tm.labels_from_status_and_resolution('closed', 'worksforme')
            )
        self.assertEqual(
            {'new'},
            tm.labels_from_status_and_resolution('new', '')
            )
        self.assertEqual(
            {},
            tm.labels_from_status_and_resolution(None, None)
            )

    def test_labels_from_type(self):
        self.assertEqual(
            ['defect', 'priority-normal'],
            tm.get_labels(t_type='defect')
            )
        self.assertEqual(
            ['priority-normal', 'release-blocker'],
            tm.get_labels(t_type='release blocker: regression')
            )


class TestAssigneeMapping(unittest.TestCase):
    """
    Trac Owners are mapped to GitHub assignees.
    """
    def test_user_mapping(self):
        self.assertEqual(['adiroiban'], tm.get_assignees('adi'))

    def test_unknown_user_mapping(self):
        self.assertEqual([], tm.get_assignees('john-doe'))

    def test_email_stripping(self):
        """
        Don't publish the e-mails of users.
        """
        self.assertEqual(
            'SomeUser', tm.get_GitHub_user('SomeUser <some@email.com>')
            )


class TestBody(unittest.TestCase):
    """
    The GitHub issue body is made from the Trac description and other fields.
    """
    def test_get_body_details(self):
        """
        Writes Trac ticket details at the beginning of the description,
        then the description and attachments if any,
        then machine-readable details at the end.

        This is a "golden test" which covers all features.
        """
        self.maxDiff = 10000

        self.assertEqual(
            "|[![adiroiban's avatar](https://avatars.githubusercontent.com/u/204609?s=50)](https://github.com/adiroiban)| @adiroiban reported|\n"
            "|-|-|\n"
            "|Trac ID|trac#4419|\n"
            "|Type|release blocker: release process bug|\n"
            "|Created|1970-01-01 00:00:00Z|\n"
            "|Last changed|1970-01-01 00:20:36Z|\n"
            "|Branch|4419-some-branch-somewhere|\n"
            "\n"
            "The ticket description. Some ```monospaced``` text.\n"
            "\n"
            "Attachments:\n"
            "\n"
            
            "* [issue4419.diff]"
            "(https://site.com/trunk/ticket/35c/35ccaee7c6ad5b60087406a818a6e0602a2a771f/8519e6a3f1bcc3fe97ba41d9367a62b3d1636845.diff)"
            " (552 bytes) - "
            "added by author_nickname on 2011-10-22 06:47:13Z - "
            "\n"
            
            "* [0001-Make-IRCClient.noticed-empty-by-default-to-avoid-loo.patch]"
            "(https://site.com/trunk/ticket/35c/35ccaee7c6ad5b60087406a818a6e0602a2a771f/e3090ff2b269e2f0b4c2e1dfacdb7ecadb36a47b.patch) "
            "(12345 bytes) - "
            "added by author_nickname2 on 2011-10-22 06:47:14Z - "
            "Simpler patch that just blanks the noticed() implementation\n"
            "\n"
            "<details><summary>Searchable metadata</summary>\n"
            "\n"
            "```\n"
            "trac-id__4419 4419\n"
            "type__release_blocker__release_process_bug release blocker: release process bug\n"
            "reporter__adi adi\n"
            "priority__some_priority some-priority\n"
            "milestone__some_milestone some-milestone\n"
            "branch__4419_some_branch_somewhere 4419-some-branch-somewhere\n"
            "branch_author__someone_like_you someone_like_you\n"
            "status__some_status some-status\n"
            "resolution__some_resolution some-resolution\n"
            "component__some_component some-component\n"
            "keywords__some_keywords some-keywords\n"
            "time__1234 1234\n"
            "changetime__1236000000 1236000000\n"
            "owner__some_owner some-owner\n"
            "version__some_version some-version\n"
            "cc__some-cc cc__other_CC cc__mail_domain_stripped\n"
            "```\n"
            "</details>\n",

            tm.get_body(
                "The ticket description. Some {{{monospaced}}} text.",
                {
                    't_id': 4419,
                    't_type': 'release blocker: release process bug',
                    'reporter': 'adi',
                    'time': 1234,
                    'changetime': 1236000000,
                    'branch': '4419-some-branch-somewhere',
                    'branch_author': 'someone_like_you',
                    'priority': 'some-priority',
                    'milestone': 'some-milestone',
                    'status': 'some-status',
                    'resolution': 'some-resolution',
                    'component': 'some-component',
                    'keywords': 'some-keywords',
                    'cc': 'some-cc, other_CC, mail_domain_stripped@cc.com',
                    'owner': 'some-owner',
                    'version': 'some-version',
                    'attachments': (
                        {
                            'filename': '0001-Make-IRCClient.noticed-empty-by-default-to-avoid-loo.patch',
                            'size': '12345',
                            'time': '1319266034000000',
                            'description': 'Simpler patch that just blanks the noticed() implementation',
                            'author': 'author_nickname2',
                            },
                        {
                            'filename': 'issue4419.diff',
                            'size': '552',
                            'time': '1319266033000000', # 2011-10-22 06:47:13Z
                            'description': '',
                            'author': 'author_nickname',
                            },
                        )
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
        Missing Trac ticket IDs are converted to trac#1234 autolinks..
        """
        self.assertEqual(
            "Some issue is solved in trac#345.",
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
            "Some issue is solved in trac#1234.",
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
        trac_data = [{
            't_id': 3928,
            'c_time': 1489439926524055,
            'author': 'mthuurne',
            'field': 'comment',
            'newvalue': 'Thanks.',
            }]
        desired_body = (
            "|[![mthuurne's avatar](https://avatars.githubusercontent.com/u/246676?s=50)](https://github.com/mthuurne)|@mthuurne commented:|\n"
            "|-|-|\n"
            "\n"
            "Thanks."
            )

        self.assertEqual(
            desired_body,
            tm.comment_from_trac_changes(
                trac_data,
                ticket_mapping={}
                )['github_comment']['body']
            )

    def test_no_user(self):
        """
        A user not defined in config.py is preserved.
        """
        trac_data = [{
            't_id': 3928,
            'c_time': 1488909819877801,
            'author': 'andradaE',
            'field': 'comment',
            'newvalue': 'Thanks.',
            }]
        desired_body = (
            "|[![andradaE's avatar](https://avatars.githubusercontent.com/u/583231?s=50)](https://github.com/andradaE)|@andradaE commented:|\n"
            "|-|-|\n"
            "\n"
            "Thanks."
            )

        self.assertEqual(
            desired_body,
            tm.comment_from_trac_changes(
                trac_data,
                ticket_mapping={}
                )['github_comment']['body']
            )

    def test_formatting(self):
        """
        Check that at least some formatting works.
        """
        trac_data = [{
            't_id': 3928,
            'c_time': 1488909819877801,
            'author': 'andradaE',
            'field': 'comment',
            'newvalue': (
                '[http://styleguide.chevah.com/tickets.html Style Guide]'
                ),
            }]
        desired_body = (
            "|[![andradaE's avatar](https://avatars.githubusercontent.com/u/583231?s=50)](https://github.com/andradaE)|@andradaE commented:|\n"
            "|-|-|\n"
            "\n"
            "[Style Guide](http://styleguide.chevah.com/tickets.html)"
            )

        self.assertEqual(
            desired_body,
            tm.comment_from_trac_changes(
                trac_data,
                ticket_mapping={},
                )['github_comment']['body']
            )

    def test_status_change(self):
        """
        A GitHub comment is created from a status change.
        """
        trac_data = [{
            't_id': 3928,
            'c_time': 1489439926524055,
            'author': 'mthuurne',
            'field': 'status',
            'newvalue': 'reopened',
            }]
        desired_body = (
            "|[![mthuurne's avatar](https://avatars.githubusercontent.com/u/246676?s=50)](https://github.com/mthuurne)|@mthuurne set status to `reopened`.|\n"
            "|-|-|\n"
            )

        self.assertEqual(
            desired_body,
            tm.comment_from_trac_changes(
                trac_data, ticket_mapping={}
                )['github_comment']['body']
            )

    def test_assignment(self):
        """
        A GitHub comment is created from an assignment to a different owner.
        """
        trac_data = {
            't_id': 3928,
            'c_time': 1489439926524055,
            'author': 'andradaE',
            'newvalue': 'mthuurne',
            }
        desired_body = (
            "@andradaE set owner to @mthuurne."
            )

        self.assertEqual(
            desired_body,
            tm.owner_change_from_trac_data(trac_data)
            )

    def test_complex(self):
        """
        A GitHub comment is created from a removal of the owner,
        a status change and a comment.
        """
        trac_data = [
            {
                't_id': 3928,
                'c_time': 1489439926524055,
                'author': 'andradaE',
                'field': 'owner',
                'newvalue': '',
                },
            {
                't_id': 3928,
                'c_time': 1489439926524055,
                'author': 'andradaE',
                'field': 'status',
                'newvalue': 'closed',
                },
            {
                't_id': 3928,
                'c_time': 1489439926524055,
                'author': 'andradaE',
                'field': 'comment',
                'newvalue': 'Finally, this is done!',
                },
            ]

        desired_body = (
            "|[![andradaE's avatar]"
            "(https://avatars.githubusercontent.com/u/583231?s=50)]"
            "(https://github.com/andradaE)|"
            "@andradaE removed owner.<br>"
            "@andradaE set status to `closed`.|\n"
            "|-|-|\n"
            "\n"
            "Finally, this is done!"
            )

        self.assertEqual(
            desired_body,
            tm.comment_from_trac_changes(
                trac_data, ticket_mapping={}
                )['github_comment']['body']
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
                'owner': 'adi',
                'status': 'closed',
                'resolution': 'wontfix',
                'milestone': 'some-milestone',
                'summary': 'summary',
                'description': 'description',
                'priority': 'high',
                'keywords': 'feature, easy',
                'reporter': 'danuker',
                't_id': 6,
                't_type': 'task',
                'time': 1288883091000000,
                'changetime': 1360238496689890,
                'branch': 'https://github.com/chevah/agent-1.5/pull/10',
                'branch_author': 'somebody_i_used_to_know',
                'cc': 'the_nsa',
                'version': '2.0',
                }],
            ticket_mapping={},
            )

        requests = list(request_gen)
        self.assertEqual(1, len(requests))
        request = requests[0]

        self.assertEqual('trac-migration-staging', request.repo)
        self.assertEqual('chevah', request.owner)
        self.assertEqual('adiroiban', request.data['assignee'])
        self.assertEqual(
            [
                'easy',
                'feature',
                'priority-high',
                'task',
                'trac-migration-staging',
                'wontfix'
                ],
            request.data['labels'])
        self.assertEqual('some-milestone', request.milestone)
        self.assertEqual('summary', request.data['title'])

        # Test just one metadata field (before `type__`).
        # The rest are tested in TestBody.
        self.assertEqual(
            "|[![danuker's avatar](https://avatars.githubusercontent.com/u/583231?s=50)](https://github.com/danuker)| @danuker reported|\n"
            '|-|-|\n'
            '|Trac ID|trac#6|\n'
            '|Type|task|\n'
            '|Created|2010-11-04 15:04:51Z|\n'
            '|Last changed|2013-02-07 12:01:36Z|\n'
            '|Branch|https://github.com/chevah/agent-1.5/pull/10|\n'
            '\n'
            'description\n'
            '\n'
            '<details><summary>Searchable metadata</summary>\n'
            '\n'
            '```\n'
            'trac-id__6 6\n',
            request.data['body'].split('type__', 1)[0])


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


if __name__ == '__main__':
    unittest.main()
