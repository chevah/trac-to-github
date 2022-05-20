#!/usr/bin/env python3
# Migrate Trac tickets to GitHub.
# Uses the Golden Comet preview (fast) API:
# https://gist.github.com/jonmagic/5282384165e0f86ef105

import datetime
import pprint
import re
import requests
import sqlite3
import sys
import time
from collections import deque, defaultdict
from itertools import chain
from typing import Union

from attachment_links import get_attachment_path
from wiki_trac_rst_convert import matches, sub

try:
    import config
except ModuleNotFoundError:
    # In the tests, we monkeypatch this module.
    config = None

from trac2down import convert

# Set to False to perform actual GitHub issue creation.
DRY_RUN = True
# DRY_RUN = False


def main():
    """
    Read the Trac DB and post the tickets to GitHub.
    """
    to_submit = list(select_tickets(read_trac_tickets()))
    submitted_already = get_tickets('tickets_created.tsv').values()
    np = NumberPredictor()
    attach_attachments(tickets=to_submit, attachments=read_trac_attachments())
    to_submit, expected_numbers = np.orderTickets(
        to_submit, already_created=submitted_already
        )

    ticket_mapping = get_ticket_mapping(to_submit, expected_numbers)
    raw_comments = chain(
        read_trac_owner_changes(),
        read_trac_status_changes(),
        read_trac_comments(),
        )
    comments_by_ticket_and_time = group_comments(raw_comments)

    comments = {
        t_id: [
            comment_from_trac_changes(
                comments_by_ticket_and_time[t_id][created_time],
                ticket_mapping
                )
            for created_time in comments_by_ticket_and_time[t_id]
            ]
        for t_id in comments_by_ticket_and_time
        }

    # Parse tickets into GitHub issue objects.
    issues = list(GitHubRequest.fromTracDataMultiple(
        to_submit, ticket_mapping=ticket_mapping
        ))

    output_stats(issues, expected_numbers)

    print("Issues parsed. Starting to submit them.\n"
          "Please don't manually open issues or PRs until this is done.")

    for issue, expected_number in zip(issues, expected_numbers):
        print(f"Processing GH {expected_number}")
        issue.submit(
            expected_number,
            all_comments=comments,
            ticket_mapping=ticket_mapping
            )

    print("Issue creation complete. You may now manually open issues and PRs.")


def group_comments(raw_comments):
    """
    Group comments by ticket and time.
    """
    comments_by_ticket = defaultdict(lambda: [])
    for c in raw_comments:
        comments_by_ticket[c['t_id']].append(c)
    comments_by_ticket_and_time = defaultdict(lambda: defaultdict(lambda: []))
    for t_id in comments_by_ticket:
        for c in comments_by_ticket[t_id]:
            comments_by_ticket_and_time[t_id][c['c_time']].append(c)
    return comments_by_ticket_and_time


def select_tickets(tickets):
    """
    Easy-to-edit method to choose tickets to submit.
    Checks that the `t_id` is not in `tickets_created.tsv`.
    Useful for creating tickets in multiple rounds.
    """
    # Skip tickets that have already been created.
    submitted_ids = get_tickets().keys()
    tickets = [t for t in tickets if t['t_id'] not in submitted_ids]

    return [t for t in tickets if t['t_id'] in [
        # 4536,  # a lot of changes
        # 4258,  # Reopened
        # 3621,  # Reopened, enhancement, link to another ticket
        # 9300,  # Reopened -> new
        # 9335,  # Reopened -> closed, milestone, code example
        # 5786,  # First comment replies to ticket
        # 6887,  # Enhancement, second comment replies to different ticket
        10027,  # By Adi, enhancement, new milestoen, fixed
        ]]
    return tickets


def get_ticket_mapping(tickets, expected_numbers):
    """
    Returns a dictionary of all known Trac ID -> GitHub URL correspondences.
    The GitHub URL may either be expected, or read from tickets_created.tsv.
    """
    mapping = get_tickets()
    expected_allrepos = get_tickets('tickets_expected_gold.tsv')
    for ticket, expected_numbers in expected_allrepos.items():
        mapping[ticket] = expected_numbers

    return mapping


def get_tickets(filename='tickets_created.tsv'):
    """
    Reads the tickets_created.tsv, and returns a dictionary of
    Trac ID -> GitHub URL of tickets that were sent to GitHub already.
    """
    created_tickets = {}
    with open(filename) as f:
        for line in f:
            if line.startswith(config.TRAC_TICKET_PREFIX):
                trac_link, github_url = line.strip().split('\t')
                trac_id = trac_link.split(config.TRAC_TICKET_PREFIX)[1]
                trac_id = int(trac_id)
                created_tickets[trac_id] = github_url
    return created_tickets


def read_trac_tickets():
    """
    Read the Trac ticket data from the database, and generate dicts.
    """
    db = get_db()

    # Select the last change for `branch` and `branch_author`.
    # In SQLite, there is no DISTINCT ON respecting order,
    # but max(time) forces the other row fields to be the most up to date.
    # https://www.sqlite.org/quirks.html#aggregate_queries_can_contain_non_aggregate_result_columns_that_are_not_in_the_group_by_clause
    ticket_branches = {}
    ticket_branch_authors = {}
    for changerow in db.execute(
            """
            SELECT max(time), ticket, field, newvalue 
            FROM ticket_change 
            WHERE field in ('branch', 'branch_author') 
            GROUP BY ticket, field;
            """
            ):
        changetime, change_ticketid, field, value = changerow
        if field == 'branch':
            ticket_branches[change_ticketid] = value
        if field == 'branch_author':
            ticket_branch_authors[change_ticketid] = value

    for row in db.execute("SELECT * FROM ticket;"):
        (
            t_id,
            t_type,
            time,
            changetime,
            component,
            severity,
            priority,
            owner,
            reporter,
            cc,
            version,
            milestone,
            status,
            resolution,
            summary,
            description,
            keywords,
            ) = row

        yield {
            't_id': t_id,
            't_type': t_type,
            'time': time,
            'changetime': changetime,
            'component': component,
            'severity': severity,
            'priority': priority,
            'owner': owner,
            'reporter': reporter,
            'cc': cc,
            'version': version,
            'milestone': milestone,
            'status': status,
            'resolution': resolution,
            'summary': summary,
            'description': description,
            'keywords': keywords,
            'branch': ticket_branches.get(t_id, ''),
            'branch_author': ticket_branch_authors.get(t_id, ''),
            }


def read_trac_comments():
    """
    Read the Trac comment data from the database.

    The last version is in the `newvalue` of the `comment` field.

    To find changed comments, check the `ticket_change` table in the DB
    for the `field` column having the value `_comment0`.
    """
    db = get_db()
    for row in db.execute(
            "SELECT * FROM ticket_change where field = 'comment';"):
        t_id, c_time, author, field, oldvalue, newvalue = row

        # Only return comments with actual truthy text.
        if newvalue:
            yield {
                't_id': t_id,
                'c_time': c_time,
                'author': author,
                'field': field,
                'oldvalue': oldvalue,
                'newvalue': newvalue,
                }


def read_trac_attachments():
    """
    Read the Trac attachment data from the database.
    """
    db = get_db()
    for row in db.execute(
            "SELECT * FROM attachment;"):
        att_type, t_id, filename, size, time, description, author, ipnr = row

        yield {
            't_id': t_id,
            'filename': filename,
            'size': size,
            'time': time,
            'description': description,
            'author': author,
            }


def read_trac_status_changes():
    """
    Read the Trac status change data from the database.
    """
    db = get_db()
    for row in db.execute(
            "SELECT * FROM ticket_change where field = 'status';"):
        ticket, c_time, author, field, oldvalue, newvalue = row

        yield {
            't_id': ticket,
            'c_time': c_time,
            'author': author,
            'field': field,
            'oldvalue': oldvalue,
            'newvalue': newvalue,
            }


def read_trac_owner_changes():
    """
    Read the Trac ticket owner changes data from the database.
    """
    db = get_db()
    for row in db.execute(
            "SELECT * FROM ticket_change where field = 'owner';"):
        ticket, c_time, author, field, oldvalue, newvalue = row

        yield {
            't_id': ticket,
            'c_time': c_time,
            'author': author,
            'field': field,
            'oldvalue': oldvalue,
            'newvalue': newvalue,
            }


def attach_attachments(tickets, attachments):
    """
    Augment each ticket entry with a list of its attachments.
    """
    tickets_to_attachments = defaultdict(lambda: [])
    for a in attachments:
        tickets_to_attachments[a['t_id']].append(a)

    for t in tickets:
        t['attachments'] = tickets_to_attachments[str(t['t_id'])]


def comment_from_trac_changes(changes, ticket_mapping):
    """
    Convert a list of ticket changes occurring at the same time
    into a GitHub comment.
    """
    # We only support one comment per change group.
    assert len([c for c in changes if c['field'] == 'comment']) <= 1, changes
    # We have at least one change.
    assert len(changes) >= 1, changes
    # All changes are at the same time.
    assert len(set(c['c_time'] for c in changes)) == 1, changes
    # All changes are on the same ticket.
    assert len(set(c['t_id'] for c in changes)) == 1, changes

    comment = {
        'oldvalue': '',
        'newvalue': '',
        't_id': changes[0]['t_id'],
        'c_time': changes[0]['c_time'],
        'author': changes[0]['author'],
        }
    comments = [c for c in changes if c['field'] == 'comment']
    if comments:
        comment = comments[0]

    # Description of actions performed.
    actions_performed = '<br>'.join(
        dispatch_ticket_change(c) for c in changes if c['field'] != 'comment'
        )
    if not actions_performed:
        author = get_GitHub_user(comment['author'])
        actions_performed = f'{tag_or_not(author)} commented'

    comment_number = comment.get('oldvalue', '').split('.')[-1]
    comment_anchor = ''
    if comment_number:
        comment_anchor = f'<a name="note_{comment_number}"></a>'

    author = get_GitHub_user(changes[0]['author'])
    comment_body = ''

    if comment['newvalue']:
        comment_body = f"\n{parse_body(comment['newvalue'], ticket_mapping)}"
    body = (
        f"|{avatar(author)}{comment_anchor}|{actions_performed}|\n"
        f"|-|-|\n"
        f"{comment_body}"
        )

    return {
        't_id': comment['t_id'],
        'github_comment': {
            'created_at': isotime(comment['c_time']), 'body': body
            }
        }


def dispatch_ticket_change(trac_data):
    """
    Calls the appropriate method to process a ticket change into a description.
    """
    if trac_data['field'] == 'status':
        return status_change_from_trac_data(trac_data)
    if trac_data['field'] == 'owner':
        return owner_change_from_trac_data(trac_data)
    raise ValueError(f'Unhandled field for data: {trac_data}')


def status_change_from_trac_data(trac_data):
    """
    Convert a ticket status change to a text description.
    """
    author = get_GitHub_user(trac_data['author'])
    return f"{tag_or_not(author)} set status to `{trac_data['newvalue']}`"


def owner_change_from_trac_data(trac_data):
    """
    Convert a ticket status change to a text description.
    """
    author = get_GitHub_user(trac_data['author'])
    owner = get_GitHub_user(trac_data['newvalue'])

    action = 'removed owner'
    if owner:
        action = f'set owner to {tag_or_not(owner)}'

    return f'{tag_or_not(author)} {action}'


def get_GitHub_user(trac_user):
    """
    Fetch a user from the config mapping, discarding the e-mail.
    If there is no GitHub user mapped, the `trac_user` argument is returned.
    """
    if trac_user is not None:
        trac_user = trac_user.replace('<automation>', 'Automation').split(' <', 1)[0]

    github_user, _ = config.USER_MAPPING.get(trac_user, (None, 'N/A'))

    if github_user:
        return github_user

    return trac_user


def tag_or_not(github_user):
    """
    Either tag/mention a user with an at-sign (`@user`) if they have a UID,
    or use their Trac name without linking, if they don't.
    """
    if github_user in config.UID_MAPPING:
        return f"@{github_user}"
    return github_user


def get_db():
    """
    Return a database connection.
    """
    if len(sys.argv) != 2:
        print("Need to pass the path to Trac DB as argument.")
        sys.exit(1)
    db = sqlite3.connect(sys.argv[1])
    return db


class NumberPredictor:
    """
    A best-effort algorithm to preserve issue IDs (named "numbers" in the API).
    """
    def __init__(self):
        """
        Store a cache of repository -> next issue numbers.
        """
        self.next_numbers = {}

    def requestNextNumber(self, repo, tickets_from_file):
        """
        Send GET requests for the latest issues and PRs,
        look at the largest number assigned so far, and increment by one.

        Remember the result in `self.next_numbers`.
        """
        if repo in self.next_numbers:
            return self.next_numbers[repo]

        last_issue_number = self._requestMaxNumber(repo, 'issues')
        last_pull_number = self._requestMaxNumber(repo, 'pulls')
        last_ticket_submitted = self.getMaxCreatedTicketNumber(
            repo, tickets_from_file)

        next_number = max(
            last_issue_number, last_pull_number, last_ticket_submitted
            ) + 1
        print(f"Next issue for {repo} will be {next_number}.")

        return next_number

    @staticmethod
    def getMaxCreatedTicketNumber(repo, ticket_urls):
        """
        Given a repository and a list of created GitHub issue URLs,
        return the largest ticket number in that repository.
        If no tickets match, return 0.
        """
        repo_urls = [
            url for url in ticket_urls
            if url.startswith(
                f'https://github.com/{config.OWNER}/{repo}/issues/'
                )
            ]
        repo_nums = [int(url.rsplit('/', 1)[1]) for url in repo_urls]

        if not repo_nums:
            return 0
        return max(repo_nums)

    @staticmethod
    def _requestMaxNumber(repo, kind):
        """
        Get the largest GitHub number, for either tickets or pulls.
        `kind` is either "issues" or "pulls".

        By default GitHub orders them newest first.

        Issue API docs:
        https://docs.github.com/en/rest/reference/issues#list-repository-issues
        PR API docs:
        https://docs.github.com/en/rest/reference/pulls#list-pull-requests
        """
        tickets_or_pulls = requests.get(
            url=f'https://api.github.com/repos/{config.OWNER}/{repo}/{kind}',
            headers={'accept': 'application/vnd.github.v3+json'},
            auth=(config.OAUTH_USER, config.OAUTH_TOKEN),
            params={'state': 'all'},
            )
        try:
            last_number = tickets_or_pulls.json()[0]['number']
        except IndexError:
            last_number = 0
        except KeyError:
            raise KeyError(
                f"Couldn't get tickets from {config.OWNER}/{repo}.\n"
                f"Response from server:\n{tickets_or_pulls.json()}\n"
                f'Note: a "not found" response may mean an expired token.'
                )

        wait_for_rate_reset(tickets_or_pulls)

        return last_number

    def orderTickets(self, tickets, already_created):
        """
        Choose an order to create tickets on GitHub so that we maximize
        matches of GitHub IDs with Trac IDs.

        Return the ticket objects in order, and their expected GitHub numbers.
        """
        repositories = [config.REPOSITORY]
        all_repo_ordered_tickets = []
        expected_github_numbers = []

        for repo in unique(repositories):
            print('processing repo', repo)
            self.next_numbers[repo] = self.requestNextNumber(
                repo, already_created)

            tickets_by_id = {t['t_id']: t for t in tickets}
            ordered_tickets = []
            not_matching = deque()

            # Remember tickets not matching, which we can use to fill gaps.
            for t_id in list(tickets_by_id.keys()):
                if t_id < self.next_numbers[repo]:
                    not_matching.append(tickets_by_id[t_id])

            start = self.next_numbers[repo]
            end = start + len(tickets_by_id)
            for github_number in range(start, end):
                # Check if we have a ticket on this position.
                ticket = tickets_by_id.pop(github_number, None)
                if ticket:
                    ordered_tickets.append(ticket)
                    continue

                try:
                    # Use non-matching tickets to fill the gap,
                    # hoping that we eventually reach a matching one.
                    ticket = not_matching.popleft()
                    ordered_tickets.append(ticket)
                except IndexError:
                    # Can't fill the gap. Sacrifice new tickets from the end.
                    t_id = max(tickets_by_id.keys())
                    ordered_tickets.append(tickets_by_id.pop(t_id))

            # Add what's left of the non-matching.
            ordered_tickets.extend(not_matching)

            # And add to the all-repo list.
            all_repo_ordered_tickets.extend(ordered_tickets)

            # Compute GitHub numbers.
            github_end = start + len(ordered_tickets)
            expected_github_numbers.extend(range(start, github_end))

        assert len(all_repo_ordered_tickets) == len(expected_github_numbers)
        return all_repo_ordered_tickets, expected_github_numbers


def unique(elements):
    """
    Discard duplicate items, while preserving order.
    """
    seen = set()
    uniques = []
    for e in elements:
        if e not in seen:
            seen.add(e)
            uniques.append(e)

    return uniques


def output_stats(tickets, expected_numbers):
    """
    Show how many tickets will preserve their Trac ID.

    Generate a file with the expected GitHub numbers.
    """
    zipped = list(zip(tickets, expected_numbers))
    with open('tickets_expected.tsv', 'w') as f:
        f.write('Trac link\tExpected GitHub link\n')
        for t, e in zipped:
            _github_link = github_link(t.repo, e)
            f.write(f"{t.trac_url()}\t{_github_link}\n")

    match_count = sum(1 for t, e in zipped if t.t_id == e)
    print('Expected GitHub numbers to match Trac ID: '
          f'{match_count} out of {len(tickets)}')
    print(
        'Check tickets_expected.tsv, and if correct, continue the debugger. '
        f'Tickets will be submitted to GitHub: {not DRY_RUN}'
        )
    import pdb
    pdb.set_trace()


def github_link(repo, expected_number):
    """
    Return the expected GitHub URL,
    given the repository name and expected GitHub issue number.
    """
    return f'https://github.com/{config.OWNER}/{repo}/issues/{expected_number}'


def avatar(user):
    """
    Insert an image of the user's avatar, and link to the account.
    Some UIDs won't scale to 50 (example: albertkoch),
    so we force it via an HTML img tag.
    """
    user_uid = config.UID_MAPPING.get(
        user,
        0  # GitHub octocat ghost (does not scale to 50).
        )
    if user_uid:
        return f"[<img alt=\"{user}'s avatar\" src=\"https://avatars.githubusercontent.com/u/{user_uid}?s=50\" width=\"50\" height=\"50\">](https://github.com/{user})"
    return f"<img alt=\"{user}'s avatar\" src=\"https://avatars.githubusercontent.com/u/0?s=50\" width=\"50\" height=\"50\">"


class GitHubRequest:
    """
    Transform Trac tickets, comments, and their metadata to GitHub format,
    and allow submitting that format.
    """
    # Cache for milestone title -> GitHub ID.
    milestones = {}

    def __init__(
            self, owner, repo, trac_id,
            title, body, closed, resolution, milestone, labels, assignees,
            created_at, updated_at
            ):
        self.owner = owner
        self.repo = repo
        self.t_id = trac_id
        self.closed = closed
        self.resolution = resolution
        self.milestone = milestone

        # Data to submit to GitHub.
        self.data = {
            'title': title,
            'body': body,
            'labels': labels,
            'closed': closed,
            'milestone': self.getOrCreateMilestone(self.milestone)
            }
        if assignees:
            self.data['assignee'] = assignees[0]
        self.data['created_at'] = created_at
        self.data['updated_at'] = updated_at
        if closed:
            # We are assuming closure is the last modification.
            self.data['closed_at'] = updated_at

        # We get the issue number and ID after submitting.
        self.github_number = None
        self.github_id = None

    def submit(self, expected_number, all_comments, ticket_mapping):
        """
        Execute the POST request to create a GitHub issue.

        In case of an unexpected state, go into debug mode.

        API Docs:
        https://gist.github.com/jonmagic/5282384165e0f86ef105#supported-issue-and-comment-fields
        Get issue ID after created:
        https://docs.github.com/en/rest/reference/issues#get-an-issue
        """
        url = f'https://api.github.com/repos/{self.owner}/{self.repo}/import/issues'
        data = {
            'issue': self.data,
            'comments': [c['github_comment'] for c in all_comments[self.t_id]]
            }

        response = protected_request(
            url=url, data=data, expected_status_code=202)

        if response:
            # Remember the GitHub URL assigned to each ticket.
            github_import_id = response.json()['id']

            while response.json()['status'] == 'pending':
                # Wait until our issue is created.
                print('Waiting for import to finish...')
                check_url = f'{url}/{github_import_id}'
                response = protected_request(
                    url=check_url,
                    data=None,
                    method=requests.get,
                    expected_status_code=200
                    )

            if response.json()['status'] != 'imported':
                response = debug_response(response)

            number = int(response.json()['issue_url'].rsplit('/', 1)[1])
            self.github_number = number
            print(f"Import {response.json()['id']} succeeded for #{number}.")

            with open('tickets_created.tsv', 'a') as f:
                github_url = (
                    f'https://github.com/{self.owner}/{self.repo}/issues/'
                    f'{self.github_number}'
                    )
                f.write(f'{self.trac_url()}\t{github_url}\n')

            if number != expected_number:
                raise ValueError(
                    f"Ticket number mismatch: "
                    f"expected {expected_number}, created {github_url}.\n"
                    f"Please manually add the comments and project of the issue, "
                    f"close the issue if needed, "
                    f"and then restart the script."
                    )
            response = protected_request(
                url=response.json()['issue_url'],
                data=None,
                method=requests.get,
                expected_status_code=200
                )
            self.github_id = response.json()['id']
            print(f"Issue #{self.github_number} has GHID {self.github_id}.")

    def trac_url(self):
        """
        Return this issue's Trac URL.
        """
        return config.TRAC_TICKET_PREFIX + str(self.t_id)

    @classmethod
    def getOrCreateMilestone(cls, title):
        """
        If a GitHub milestone exists named like the Trac one, return its ID,
        otherwise create it and return its ID.
        Remembers milestones in `milestones_created.tsv`.

        API docs:
        https://docs.github.com/en/rest/issues/milestones#create-a-milestone
        """
        if not title:
            # Some tickets don't have a milestone.
            return

        if title in cls.milestones:
            return cls.milestones[title]

        # Check whether we have already created the project.
        with open('milestones_created.tsv') as f:
            projects_data = [line.split('\t') for line in f]
            for line_title, number in projects_data:
                if line_title == title:
                    cls.milestones[title] = int(number)
                    return int(number)

        # We have not created the project. Create it.
        response = protected_request(
            url=f'https://api.github.com/repos/{config.OWNER}/{config.REPOSITORY}/milestones',
            data={'title': title}
            )
        milestone_number = response.json()['number']

        with open('milestones_created.tsv', 'a') as f:
            f.write('\t'.join([title, str(milestone_number)]) + '\n')

        cls.milestones[title] = milestone_number
        return milestone_number

    @classmethod
    def fromTracData(
            cls,
            ticket_mapping,
            **kwargs):
        """
        Create a GitHubRequest from Trac ticket data fields.
        """
        desired_assignees = get_assignees(kwargs['owner'])
        assignees = [
            a for a in desired_assignees if a in config.ASSIGNABLE_USERS
            ]

        return cls(
            owner=config.OWNER,
            repo=config.REPOSITORY,
            trac_id=kwargs['t_id'],
            title=kwargs['summary'],
            body=get_body(
                kwargs['description'],
                data=kwargs,
                ticket_mapping=ticket_mapping
                ),
            closed=kwargs['status'] == 'closed',
            resolution=kwargs['resolution'],
            milestone=kwargs['milestone'],
            labels=get_labels(**kwargs),
            assignees=assignees,
            created_at=isotime(kwargs['time']),
            updated_at=isotime(kwargs['changetime'])
            )

    @classmethod
    def fromTracDataMultiple(cls, trac_data, ticket_mapping):
        """
        Generate GitHubRequests from an iterable of dicts of Trac tickets.
        """
        for ticket in trac_data:
            yield cls.fromTracData(
                **{**ticket, 'ticket_mapping': ticket_mapping}
                )


def protected_request(
        url, data, method=requests.post, expected_status_code=201, debug=True):
    """
    Send a request if DRY_RUN is not truthy.

    In case of error, start the debugger.
    In case of nearing rate limit, sleep until it resets.
    """

    if DRY_RUN and debug:
        print(f"Would call {method} on {url} with data:")
        pprint.pprint(data)
        return

    # Import takes more than 0.2 seconds. Avoid checking excessively.
    # There is a risk of GitHub reporting that the import job is done,
    # but accessing the issue immediately after returns a 404.
    # Also, there may be a risk of secondary rate limit:
    # https://docs.github.com/en/rest/guides/best-practices-for-integrators#dealing-with-secondary-rate-limits
    time.sleep(0.5)

    response = method(
        url=url,
        headers={'accept': 'application/vnd.github.golden-comet-preview+json'},
        json=data,
        auth=(config.OAUTH_USER, config.OAUTH_TOKEN)
        )

    if response.status_code != expected_status_code and debug:
        print(f'Error: {method} request failed!')
        debug_response(response)

    wait_for_rate_reset(response)

    return response


def debug_response(response):
    """
    Debug a response from a server.
    """
    print(response)
    pprint.pprint(dict(response.headers))
    pprint.pprint(response.json())
    import pdb
    pdb.set_trace()
    print('Done debugging!')
    return response


def wait_for_rate_reset(response):
    """
    Wait for a rate limit reset in case it is near exhaustion.
    """
    remaining = int(response.headers['X-RateLimit-Remaining'])
    reset_time = int(response.headers['X-RateLimit-Reset'])
    if remaining < 50:
        to_sleep = int(1 + reset_time - time.time())
        print(
            f"Waiting {to_sleep / 60} minutes "
            f"(until {reset_time}) for rate limit reset.")
        time.sleep(to_sleep)


def get_body(description, data, ticket_mapping):
    """
    Generate the ticket description body for GitHub.
    """
    reporter = get_GitHub_user(data['reporter'])

    branch_message = ''
    if data['branch']:
        branch_message = f"|Branch|{data['branch']}|\n"

    attachments_message = ''
    if 'attachments' in data and data['attachments']:
        attachment_links_message = format_attachments(
            ticket_id=data['t_id'],
            attachment_list=data['attachments'])
        attachments_message = f"\n\n" \
                              f"Attachments:\n" \
                              f"\n" \
                              f"{attachment_links_message}"

    body = (
        f"|{avatar(reporter)}| {tag_or_not(reporter)} reported|\n"
        f"|-|-|\n"
        f"|Trac ID|trac#{data['t_id']}|\n"
        f"|Type|{data['t_type']}|\n"
        f"|Created|{showtime(data['time'])}|\n"
        f"{branch_message}"
        "\n"
        f"{parse_body(description, ticket_mapping)}"
        f"{attachments_message}"
        f"{format_metadata(data)}"
        )

    return body


def get_labels(
        component=None,
        priority=None,
        keywords=None,
        status=None,
        resolution=None,
        t_type=None,
        **kwargs):
    """
    Given the Trac component, priority, keywords, and resolution,
    return the labels to apply on the GitHub issue.
    """
    priority_label = labels_from_priority(priority)
    type_labels = labels_from_type(t_type)
    keyword_labels = labels_from_keywords(keywords)
    component_labels = labels_from_component(component)
    status_labels = labels_from_status_and_resolution(status, resolution)
    labels = (
        {priority_label}.union(
            type_labels).union(
            keyword_labels).union(
            component_labels).union(
            status_labels)
        )
    return sorted(labels)


def labels_from_type(ticket_type):
    if not ticket_type:
        return {}

    if ticket_type.startswith('release blocker'):
        return {'release-blocker'}

    return {ticket_type}


def get_assignees(owner):
    """
    Map the owner to the GitHub account as assignee.
    """
    owner = get_GitHub_user(owner)
    if owner in config.ASSIGNABLE_USERS:
        return [owner]
    return []


def showtime(unix_usec):
    """
    Convert a Trac timestamp to a human-readable date and time.

    Trac stores timestamps as microseconds since Epoch.
    """
    timestamp = unix_usec // 1_000_000
    dt = datetime.datetime.utcfromtimestamp(timestamp)
    return f"{dt.isoformat(sep=' ')}Z"


def isotime(unix_usec):
    """
    Convert a Trac timestamp to a ISO 8601 date and time
    fit for GitHub timestamps.

    Trac stores timestamps as microseconds since Epoch.
    """
    timestamp = unix_usec // 1_000_000
    dt = datetime.datetime.utcfromtimestamp(timestamp)
    return f"{dt.isoformat(sep='T')}Z"


def labels_from_component(component: str):
    """
    Given the Trac component,
    choose the labels to apply on the GitHub issue, if any.
    """
    if not component:
        return []

    return [component]


def labels_from_keywords(keywords: Union[str, None]):
    """
    Given the Trac `keywords` string, clean it up and parse it into a list.
    """
    if keywords is None:
        return []

    keywords = keywords.replace(',', ' ')
    keywords = keywords.split(' ')

    return [kw for kw in keywords if kw]


def labels_from_priority(priority):
    """
    Interpret None (missing) priority as normal
    (because it is the most frequent in DB counts).
    """
    if priority is None:
        return 'priority-normal'
    return 'priority-{}'.format(priority.lower())


def labels_from_status_and_resolution(status, resolution):
    """
    The resolution of a closed ticket is used, if there is one.
    The resolution can be "fixed", "duplicate", "invalid", or "wontfix".

    If the ticket is not closed, the status is used,
    if the status is not "assigned", "new", or "closed".
    """
    if status == 'closed' and resolution:
        return {resolution}

    if status:
        return {status}

    # There is no status nor resolution.
    return {}


def format_attachments(ticket_id, attachment_list):
    """
    Convert attachment data into a human-readable markdown list.
    """
    return '\n'.join(
        f"* "
        f"[{attachment['filename']}]"
        f"({get_attachment_path(config.ATTACHMENT_ROOT, ticket_id, attachment['filename'])})"
        f" ({attachment['size']} bytes) - "
        f"added by {attachment['author']} "
        f"on {showtime(int(attachment['time']))} - "
        f"{attachment['description']}"
        for attachment in sorted(attachment_list, key=lambda a: a['time'])
        )


def sanitize_email(user):
    """
    Sanitize emails like Trac, by removing the domain.
    """
    return user.split('@', 1)[0]


def format_metadata(ticket_data):
    """
    Output a machine-readable section out of the ticket data.
    """
    fields = (
        't_id '
        't_type '
        'reporter '
        'priority '
        'milestone '
        'branch '
        'branch_author '
        'status '
        'resolution '
        'component '
        'keywords '
        'time '
        'changetime '
        'version'
        )

    def rename(field):
        mappings = {'t_id': 'trac-id', 't_type': 'type'}
        return mappings.get(field, field)

    def process(value):
        """
        Replace everything with underscores, for GitHub searchability.
        Then append the original value, to preserve meaning.
        """
        original = value
        value = re.sub('[^a-zA-Z0-9]', '_', str(original))
        return f'{value} {original}'

    renamed_data = {
        rename(k): process(ticket_data[k])
        for k in fields.split()
        }

    formatted = '\n'.join(f'{k}__{v}' for k, v in renamed_data.items())
    cc_input = ticket_data['cc'].split(', ') if ticket_data['cc'] else ''
    cc_output = ' '.join(f'cc__{sanitize_email(user)}' for user in cc_input)
    sanitized_owner = process(sanitize_email(ticket_data["owner"]))
    owner = f'owner__{sanitized_owner}'
    return (
        '\n'
        '\n'
        '<details><summary>Searchable metadata</summary>\n'
        '\n'
        '```\n'
        f'{formatted}\n'
        f'{cc_output}\n'
        f'{owner}\n'
        '```\n'
        '</details>\n'
        )


def parse_body(description, ticket_mapping):
    """
    Parses text with curly-bracketed or backtick-surrounded monospace.
    Converts the curly brackets to backtick brackets.
    """
    if not description:
        return ''

    def found(index):
        """Return true if an index represents a found position in a string."""
        return index != -1

    def is_first_index(a, b):
        """
        Returns true if index a occurs before b, or if b does not exist.
        """
        return found(a) and (not found(b) or b > a)

    min_backtick = description.find('`')
    min_curly = description.find('{{{')

    if is_first_index(min_curly, min_backtick):
        return (
            convert_issue_content(description[:min_curly], ticket_mapping) +
            parse_curly(description[min_curly:], ticket_mapping)
            )

    if is_first_index(min_backtick, min_curly):
        return (
            convert_issue_content(description[:min_backtick], ticket_mapping) +
            parse_backtick(description[min_backtick:], ticket_mapping)
            )

    return convert_issue_content(description, ticket_mapping)


def convert_issue_content(text, ticket_mapping):
    """
    Convert TracWiki text to GitHub Markdown.
    Change the ticket IDs to GitHub URLs according to the mapping.
    Ignore included images.
    """
    text = text.replace(config.TRAC_TICKET_PREFIX, '#')
    ticket_re = '#([0-9]+)'
    for match in matches(ticket_re, text):
        try:
            github_url = ticket_mapping[int(match)]
            new_ticket_id = github_url.rsplit('/', 1)[1]
            text = sub(
                f'#{match}',
                f'[#{new_ticket_id}]({github_url})',
                text
                )
        except KeyError:
            # We don't know this ticket. Warn about it.
            print(
                f"Warning: ticket #{match} not in tickets_expected_gold.tsv"
                f" - using trac#{match}")
            text = sub(f'#{match}', f'trac#{match}', text)

    return convert(text, base_path='')


def parse_curly(description, ticket_mapping):
    """
    Interpret curly brackets:

    - If a #!rst marker is the first token,
    remove the brackets and return the text inside.

    - Otherwise, convert the brackets to triple backticks.
    Leave text as is until the closing curly brackets,
    which are again converted to triple backticks.
    After that, let parse_body continue.
    """
    if not description.startswith('{{{'):
        raise ValueError('Desc starts with ', description[:10])
    ending = description.find('}}}') + 3
    content = description[3:ending-3]

    if content.strip().startswith('#!rst'):
        return (
            content.split('#!rst', 1)[1] +
            parse_body(description[ending:], ticket_mapping)
            )

    if content.strip().startswith('#!python'):
        return (
            '```python' +
            content.split('#!python', 1)[1] +
            '```' +
            parse_body(description[ending:], ticket_mapping)
            )

    return (
        '```' + content + '```' +
        parse_body(description[ending:], ticket_mapping)
        )


def parse_backtick(description, ticket_mapping):
    """
    Leave text as is until the closing backtick.
    After that, let parse_body continue.
    """
    if not description.startswith('`'):
        raise ValueError('Desc starts with ', description[:10])
    description = description[1:]
    ending = description.find('`') + 1
    return (
        '`' + description[:ending] +
        parse_body(description[ending:], ticket_mapping)
        )


if __name__ == '__main__':
    main()
