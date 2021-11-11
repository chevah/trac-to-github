#!/usr/bin/env python3
# Migrate Trac tickets to GitHub.
# Uses the Golden Comet preview API:
# https://gist.github.com/jonmagic/5282384165e0f86ef105

import datetime
import pprint
import requests
import sqlite3
import sys
import time
from collections import deque
from typing import Union

from wiki_trac_rst_convert import matches, sub

try:
    import config
except ModuleNotFoundError:
    # In the tests, we monkeypatch this module.
    config = None

from trac2down import convert

# Set to False to perform actual GitHub issue creation.
DRY_RUN = True


def main():
    """
    Read the Trac DB and post the tickets to GitHub.
    """
    to_submit = list(select_tickets(read_trac_tickets()))
    comments = list(read_trac_comments())
    submitted_already = get_tickets('tickets_created.tsv').values()
    np = NumberPredictor()
    to_submit, expected_numbers = np.orderTickets(
        to_submit, already_created=submitted_already
        )

    ticket_mapping = get_ticket_mapping(to_submit, expected_numbers)

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
        issue.submitToProject()

    print("Issue creation complete. You may now manually open issues and PRs.")


def select_tickets(tickets):
    """
    Easy-to-edit method to choose tickets to submit.
    Checks that the `t_id` is not in `tickets_created.tsv`.
    Useful for creating tickets in multiple rounds.
    """
    # Skip tickets that have already been created.
    submitted_ids = get_tickets().keys()
    tickets = [t for t in tickets if t['t_id'] not in submitted_ids]

    # return [t for t in tickets if t['t_id'] == 15]
    # return [t for t in tickets if t['component'] == 'pr'] # DONE
    # return [t for t in tickets if t['component'] == 'webadmin'] # DONE
    # return [t for t in tickets if t['component'] == 'libs'] # DONE
    # return [t for t in tickets if t['component'] == 'infrastructure'] # DONE
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
            raise KeyError(f"Couldn't get tickets from {config.OWNER}/{repo}.")

        wait_for_rate_reset(tickets_or_pulls)

        return last_number

    def orderTickets(self, tickets, already_created):
        """
        Choose an order to create tickets on GitHub so that we maximize
        matches of GitHub IDs with Trac IDs.

        Return the ticket objects in order, and their expected GitHub numbers.
        """
        repositories = (
            [config.REPOSITORY_MAPPING[k] for k in config.REPOSITORY_MAPPING] +
            [config.FALLBACK_REPOSITORY]
            )
        all_repo_ordered_tickets = []
        expected_github_numbers = []

        for repo in unique(repositories):
            print('processing repo', repo)
            self.next_numbers[repo] = self.requestNextNumber(
                repo, already_created)

            tickets_by_id = {
                t['t_id']: t
                for t in select_tickets_for_repo(tickets, repo)}
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


def select_tickets_for_repo(tickets, repo: str):
    """
    From a list of Trac tickets,
    select the ones that will be posted to a given GitHub repository.
    """
    return [t for t in tickets if get_repo(t['component']) == repo]


def get_repo(component):
    """
    Given the Trac component,
    choose the GitHub repository to create the issue in.
    """
    return config.REPOSITORY_MAPPING.get(component, config.FALLBACK_REPOSITORY)


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
    print('Check tickets_expected.tsv, and if correct, continue the debugger.')
    import pdb
    pdb.set_trace()


def github_link(repo, expected_number):
    """
    Return the expected GitHub URL,
    given the repository name and expected GitHub issue number.
    """
    return f'https://github.com/{config.OWNER}/{repo}/issues/{expected_number}'


class GitHubRequest:
    """
    Transform Trac tickets, comments, and their metadata to GitHub format,
    and allow submitting that format.
    """
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
        self.data = {
            'title': title,
            'body': body,
            'labels': labels,
            'closed': closed,
            }
        if assignees:
            self.data['assignee'] = assignees[0]

        # We used updated_at, because some tickets were repurposed,
        # and it was more meaningful as the GitHub created_at.
        self.data['created_at'] = updated_at
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
            'comments': []
            }

        for comment in (c for c in all_comments if c['t_id'] == self.t_id):
            data['comments'].append(
                self.commentFromTracData(
                    comment, ticket_mapping=ticket_mapping
                    )
                )

        response = protected_request(
            url=url, data=data, expected_status_code=202)

        if response:
            # Remember the GitHub URL assigned to each ticket.
            self.github_import_id = response.json()['id']

            while response.json()['status'] == 'pending':
                # Wait until our issue is created.
                print('Waiting for import to finish...')
                check_url = f'{url}/{self.github_import_id}'
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

    def getOrCreateProject(self):
        """
        If a project for the given milestone exists, return its column IDs,
        otherwise create it and return its column IDs.
        Remembers projects in `projects_created.tsv`.

        API docs:
        https://docs.github.com/en/rest/reference/projects#create-an-organization-project
        https://docs.github.com/en/rest/reference/projects#create-a-project-column
        """
        name = self.milestone
        if not name:
            # Some tickets don't have a milestone.
            return

        # Check whether we have already created the project.
        with open('projects_created.tsv') as f:
            projects_data = [line.split('\t') for line in f]
            for line_name, _, todo_id, done_id, rejected_id in projects_data:
                if line_name == name:
                    return todo_id, done_id, rejected_id

        # We have not created the project. Create it.
        response = protected_request(
            url=f'https://api.github.com/orgs/{config.PROJECT_ORG}/projects',
            data={'name': name}
            )
        project_id = response.json()['id']
        columns_url = response.json()['columns_url']

        # Create 3 columns: To Do, Done, and Rejected.
        todo_resp = protected_request(columns_url, data={'name': 'To Do'})
        done_resp = protected_request(columns_url, data={'name': 'Done'})
        rejected_resp = protected_request(columns_url, data={
            'name': 'Rejected', 'body': 'duplicate, invalid, or wontfix'})

        # Close the project.
        protected_request(
            url=f'https://api.github.com/projects/{project_id}',
            data={'state': 'closed'},
            method=requests.patch,
            expected_status_code=200,
            )

        todo_id = todo_resp.json()['id']
        done_id = done_resp.json()['id']
        rejected_id = rejected_resp.json()['id']

        with open('projects_created.tsv', 'a') as f:
            f.write('\t'.join([
                name,
                str(project_id),
                str(todo_id),
                str(done_id),
                str(rejected_id),
                ]) + '\n')

        return todo_id, done_id, rejected_id

    def submitToProject(self):
        """
        Add an issue identified by the GitHub global `id`
        to the proper column of the proper project.

        API docs (very bad ones):
        https://docs.github.com/en/rest/reference/projects#create-a-project-card
        """
        column_ids = self.getOrCreateProject()
        if not column_ids:
            return

        todo_id, done_id, rejected_id = column_ids

        # Set the column ID according to issue status and resolution.
        column_id = todo_id
        if self.closed:
            column_id = rejected_id
            if self.resolution == 'fixed':
                column_id = done_id

        url = f'https://api.github.com/projects/columns/{column_id}/cards'
        data = {
            'content_id': self.github_id,
            'content_type': 'Issue'
            }
        protected_request(url, data)

    @classmethod
    def fromTracData(
            cls,
            component,
            owner,
            summary,
            description,
            priority,
            keywords,
            ticket_mapping,
            **kwargs):
        """
        Create a GitHubRequest from Trac ticket data fields.
        """
        return cls(
            owner=config.OWNER,
            repo=get_repo(component),
            trac_id=kwargs['t_id'],
            title=summary,
            body=get_body(
                description, data=kwargs, ticket_mapping=ticket_mapping),
            closed=kwargs['status'] == 'closed',
            resolution=kwargs['resolution'],
            milestone=kwargs['milestone'],
            labels=get_labels(
                component,
                priority,
                keywords,
                kwargs['status'],
                kwargs['resolution']
                ),
            assignees=get_assignees(owner),
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

    @staticmethod
    def commentFromTracData(trac_data, ticket_mapping):
        """
        Convert Trac comment data to GitHub comment body as JSON.
        """
        author, _ = config.USER_MAPPING.get(
            trac_data['author'],
            (trac_data['author'], 'ignored-email-field')
            )

        body = (
            f"Comment by {author} at {showtime(trac_data['c_time'])}.\n"
            f"\n"
            f"{parse_body(trac_data['newvalue'], ticket_mapping)}"
            )

        return {'created_at': isotime(trac_data['c_time']), 'body': body}


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

    # Import takes more than 0.2 seconds. Avoid checking excessively.
    # There is a risk of GitHub reporting that the import job is done,
    # but accessing the issue immediately after returns a 404.
    # Also, there may be a risk of secondary rate limit:
    # https://docs.github.com/en/rest/guides/best-practices-for-integrators#dealing-with-secondary-rate-limits
    time.sleep(0.2)

    response = method(
        url=url,
        headers={'accept': 'application/vnd.github.golden-comet-preview+json'},
        json=data,
        auth=(config.OAUTH_USER, config.OAUTH_TOKEN)
        )

    if response.status_code != expected_status_code:
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
    reporters = get_assignees(data['reporter'])
    if reporters:
        reporter = reporters[0]
    else:
        reporter = data['reporter']

    changed_message = ''
    if data['changetime'] != data['time']:
        changed_message = f"Last changed on {showtime(data['changetime'])}.\n"

    pr_message = ''
    if data['branch']:
        pr_message = f"PR at {data['branch']}.\n"

    body = (
        f"trac-{data['t_id']} {data['t_type']} was created by @{reporter}"
        f" on {showtime(data['time'])}.\n"
        f"{changed_message}"
        f"{pr_message}"
        "\n"
        f"{parse_body(description, ticket_mapping)}"
        )

    return body


def get_labels(component, priority, keywords, status, resolution):
    """
    Given the Trac component, priority, keywords, and resolution,
    return the labels to apply on the GitHub issue.
    """
    priority_label = labels_from_priority(priority)
    keyword_labels = labels_from_keywords(keywords)
    component_labels = labels_from_component(component)
    status_labels = labels_from_status_and_resolution(status, resolution)
    labels = (
        {priority_label}.union(
            keyword_labels).union(
            component_labels).union(
            status_labels)
        )
    return sorted(labels)


def get_assignees(owner):
    """
    Map the owner to the GitHub account.
    """
    try:
        owner, _ = config.USER_MAPPING.get(owner)
        return [owner]
    except TypeError as error:
        if 'cannot unpack non-iterable NoneType object' in str(error):
            return []
        raise


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
    if component in config.REPOSITORY_MAPPING:
        return []

    return [component]


def labels_from_keywords(keywords: Union[str, None]):
    """
    Given the Trac `keywords` string, clean it up and parse it into a list.
    """
    if keywords is None:
        return set()

    keywords = keywords.replace(',', '')
    keywords = keywords.split(' ')

    allowed_keyword_labels = {
        'design',
        'easy',
        'feature',
        'happy-hacking',
        'onboarding',
        'password-management',
        'perf-test',
        'remote-management',
        'salt',
        'scp',
        'security',
        'tech-debt',
        'twisted',
        'ux',
        'Adwords', 'Bing', 'PPC',
        'brink',
        'cdp',
        'cisco',
        'docker',
        'Documentation',
        'email',
        'events',
        'lets-encrypt',
        'macos', 'bind',
        'remote-manager',
        'syslog',
        'backup',
        'vpn',
        'file-server',
        'website',
        'windows', 'testing',
        }
    typo_fixes = {'tech-dept': 'tech-debt', 'tech-deb': 'tech-debt'}

    keywords = [typo_fixes.get(kw, kw) for kw in keywords if kw]
    discarded = [kw for kw in keywords if kw not in allowed_keyword_labels]

    if discarded:
        print("Warning: discarded keywords:", discarded)

    return {kw for kw in keywords if kw in allowed_keyword_labels}


def labels_from_priority(priority):
    """
    Interpret None (missing) priority as Low.
    """
    if priority is None:
        return 'priority-low'
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

    if status in ['in_work', 'needs_changes', 'needs_merge', 'needs_review']:
        return {status.replace('_', '-')}

    return set()


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
            # We don't know this ticket. Leave it alone.
            print("Warning: unknown ticket: #" + str(match))
            pass

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
