#!/usr/bin/env python3

# Comment on the issues with the PR code link,
# so that the GH PR page backlinks to the issue.

# This is done with the official API, not the bulk API,
# because the bulk API triggers no backlinks.
import datetime
import pprint
import re

import requests
import sqlite3
import sys
import time

try:
    import config
except ModuleNotFoundError:
    # In the tests, we monkeypatch this module.
    config = None
# Set to False to perform actual GitHub issue creation.
DRY_RUN = True


def main():
    """
    Read the Trac DB and tickets on GitHub,
    and link from them to their PRs.
    """
    tickets = list(select_tickets(read_trac_tickets()))
    ticket_mapping = get_tickets()

    # Parse tickets into GitHub CommentRequest objects.
    comments = list(CommentRequest.fromTracDataMultiple(
        tickets, ticket_mapping=ticket_mapping
        ))

    print("Issues parsed. Starting to submit comments.")

    for comment in comments:
        print(f"Linking GH {comment.getGitHubLink()}")
        comment.submit_link_to_pr()

    print("Issue creation complete. You may now manually open issues and PRs.")


def select_tickets(tickets):
    """
    Easy-to-edit method to choose tickets to submit.
    Checks that the `t_id` is not in `tickets_created.tsv`.
    Useful for creating tickets in multiple rounds.
    """
    # Skip tickets that have NOT already been created.
    # Only comment on already created tickets.
    submitted_ids = get_tickets().keys()
    tickets = [t for t in tickets if t['t_id'] in submitted_ids]
    tickets = [t for t in tickets if t['t_id'] == 2936]

    # Only comment on tickets which have a branch (PR linked from Trac).
    tickets = [t for t in tickets if t['branch']]

    # Skip tickets where we have already linked the PR.
    tickets = [
        t for t in tickets
        if t['t_id'] not in get_tickets('links_created.tsv')]

    # Skip tickets created with the classic API which linked the PRs.
    return [t for t in tickets if t['component'] != 'pr']

    return tickets


def get_tickets(filename='tickets_created.tsv'):
    """
    Reads the tickets_create.tsv, and returns a dictionary of
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

    # Only take the last branch change.
    # For example, https://trac.chevah.com/ticket/85 has multiple changes,
    # and the last one is to GH PR 238.
    # We use GROUP BY because SQLite has no DISTINCT ON.
    # https://www.sqlite.org/quirks.html#aggregate_queries_can_contain_non_aggregate_result_columns_that_are_not_in_the_group_by_clause
    for row in db.execute(
            """\
            SELECT *
            FROM
              (SELECT *
               FROM ticket
               LEFT JOIN ticket_change ON ticket.id = ticket_change.ticket
               AND ticket_change.field = 'branch'
               AND ticket_change.newvalue LIKE '%github%'
               ORDER BY ticket.id,
                        ticket_change.time DESC)
            GROUP BY id;
            """):
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
            _ticket,
            _time,
            _author,
            _field,
            _oldvalue,
            _newvalue,
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
            'branch': _newvalue,
            }


def get_db():
    """
    Return a database connection.
    """
    if len(sys.argv) != 2:
        print("Need to pass the path to Trac DB as argument.")
        sys.exit(1)
    db = sqlite3.connect(sys.argv[1])
    return db


class CommentRequest:
    """
    Store what is needed for a comment that links an issue to a PR.
    `pr_link` maps to the `branch` of a ticket read from the Trac DB.
    """
    def __init__(
            self, trac_id, repo, github_number, pr_link):
        self.repo = repo
        self.t_id = trac_id
        self.github_number = github_number
        self.github_pr_link = pr_link

    def submit_link_to_pr(self):
        """
        Send a POST request to GitHub creating the comment.

        API Docs:
        https://docs.github.com/en/rest/reference/issues#create-an-issue-comment
        """
        response = protected_request(
            url=self.commentsURL(), data={'body': self.commentText()}
            )

        if response:
            # Remember the GitHub URL assigned to each ticket.
            with open('links_created.tsv', 'a') as f:
                comment_url = response.json()['html_url']
                f.write(f'{self.getTracURL(self.t_id)}\t{comment_url}\n')

    def commentText(self):
        """
        Convert Trac comment data to GitHub comment body as JSON.
        """
        return f'PR for trac-{self.t_id} is at {self.github_pr_link}.'

    def getGitHubLink(self):
        """
        Return the GitHub URL,
        given the repository name and expected GitHub issue number.
        """
        return f'https://github.com/' \
               f'{config.OWNER}/{self.repo}/issues/{self.github_number}'

    @staticmethod
    def getTracURL(trac_id):
        """
        Return this issue's Trac URL.
        """
        return config.TRAC_TICKET_PREFIX + str(trac_id)

    @classmethod
    def fromTracDataMultiple(cls, trac_data, ticket_mapping):
        """
        Generate `CommentRequest`s from an iterable of dicts of Trac tickets.
        """
        for ticket in trac_data:
            github_link = ticket_mapping[ticket['t_id']]
            yield cls.fromTracData(
                t_id=ticket['t_id'],
                repo=get_repo(github_link),
                github_number=get_github_number(github_link),
                branch=ticket['branch'],
                )

    @classmethod
    def fromTracData(
            cls,
            t_id,
            repo,
            github_number,
            branch,
            ):
        """
        Create a GitHubRequest from Trac ticket data fields.
        """
        issue = cls(
            trac_id=t_id,
            repo=repo,
            github_number=github_number,
            pr_link=branch,
            )
        return issue

    def commentsURL(self):
        return f'https://api.github.com/repos/' \
               f'{config.OWNER}/{self.repo}/issues/{self.github_number}/comments'


def get_repo(github_link):
    """
    Given the GitHub link, return its repository.
    """
    match = re.match(
        f'https://github.com/{config.OWNER}/(.+)/issues/[0-9]+',
        github_link,
        )
    return match.groups()[0]


def get_github_number(github_link) -> str:
    """
    Given the GitHub link, return its issue number.
    """
    return github_link.rsplit('/', 1)[1]


def protected_request(
        url, data, method=requests.post, expected_status_code=201):
    """
    Send a request if DRY_RUN is not truthy.

    In case of error, start the debugger.
    In case of nearing rate limit, sleep until it resets.
    """

    if DRY_RUN:
        print(f"Would call {method} on {url} with data:")
        pprint.pprint(data)
        return

    # Obey secondary rate limit:
    # https://docs.github.com/en/rest/guides/best-practices-for-integrators#dealing-with-secondary-rate-limits
    time.sleep(10)

    response = method(
        url=url,
        headers={'accept': 'application/vnd.github.v3+json'},
        json=data,
        auth=(config.OAUTH_USER, config.OAUTH_TOKEN)
        )

    if response.status_code != expected_status_code:
        print('Error: POST request failed!')
        print(response)
        pprint.pprint(response.json())
        import pdb
        pdb.set_trace()

    wait_for_rate_reset(response)

    return response


def wait_for_rate_reset(response):
    """
    Wait for a rate limit reset in case it is near exhaustion.
    """
    remaining = int(response.headers['X-RateLimit-Remaining'])
    reset_time = int(response.headers['X-RateLimit-Reset'])
    if remaining < 10:
        to_sleep = int(1 + reset_time - time.time())
        print(
            f"Waiting {to_sleep}s (until {reset_time}) for rate limit reset.")
        time.sleep(to_sleep)


if __name__ == '__main__':
    main()
