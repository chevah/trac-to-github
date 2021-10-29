#!/usr/bin/env python3
# Migrate Trac tickets to GitHub.
import datetime
import sqlite3
import sys
from collections import deque
from time import sleep
from typing import Union

import requests

import config
from trac2down import convert

# Set to False to perform actual GitHub issue creation.
DRY_RUN = True


def main():
    """
    Read the Trac DB and post the open tickets to GitHub.
    """
    tickets = list(select_tickets(read_trac_tickets()))
    comments = list(read_trac_comments())
    np = NumberPredictor()
    tickets, expected_numbers = np.orderTickets(tickets)

    # Parse tickets into GitHub issue objects.
    issues = list(GitHubRequest.fromTracDataMultiple(tickets))

    output_stats(issues, expected_numbers)

    print("Issues parsed. Starting to submit them.\n"
          "Please don't manually open issues or PRs until this is done.")

    for issue, expected_number in zip(issues, expected_numbers):
        issue.submit(expected_number)

    print("Issue creation complete. "
          "You may now manually open issues and PRs.\n"
          "Continuing with comments and closing the closed tickets.")
    for issue in issues:
        issue.closeIfNeeded()
        issue.submitMyComments(comments)


def select_tickets(tickets):
    """
    Choose only tickets which don't have a closed status.
    """
    return [t for t in tickets if t['t_id'] == 5519]
    # return [t for t in tickets if t['status'] != 'closed']


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

    Example changed comment: https://trac.chevah.com/ticket/3928#comment:1
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

    def requestNextNumber(self, repo):
        """
        Send GET requests for the latest issues and PRs,
        look at the largest number assigned so far, and increment by one.

        Remember the result in `self.next_numbers`.
        """
        if repo in self.next_numbers:
            return self.next_numbers[repo]

        last_issue_number = self._requestMaxNumber(repo, 'issues')
        last_pull_number = self._requestMaxNumber(repo, 'pulls')

        next_number = max(last_issue_number, last_pull_number) + 1
        print(f"Next issue for {repo} will be {next_number}.")

        return next_number

    @staticmethod
    def _requestMaxNumber(repo, kind):
        """
        Get the largest GitHub number, for either tickets or pulls.
        `kind` is either "issues" or "pulls".
        Fortunately GitHub orders them newest first.
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

        return last_number

    def orderTickets(self, tickets):
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
            self.next_numbers[repo] = self.requestNextNumber(repo)

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
    zipped = zip(tickets, expected_numbers)
    with open('tickets_expected.tsv', 'w') as f:
        f.write('Trac link\tExpected GitHub link\n')
        for t, e in zipped:
            f.write(f"{t.trac_url()}\t{e}")

    matches = sum(1 for t, e in zipped if t['t_id'] == e)
    zipped_open = [(t, e) for t, e in zipped if
                   t['status'] != 'closed']
    matches_open = sum(1 for t, e in zipped_open if t['t_id'] == e)
    print('Expected GitHub numbers to equal Trac ID:')
    print(f'\t{matches} out of {len(tickets)}')
    print(f'\t{matches_open} out of {len(zipped_open)} open tickets\n')


class GitHubRequest:
    """
    Transform Trac tickets, comments, and their metadata to GitHub format,
    and allow submitting that format.
    """
    def __init__(
            self, owner, repo, trac_id,
            title, body, closed, milestone, labels, assignees):
        self.owner = owner
        self.repo = repo
        self.t_id = trac_id
        self.closed = closed
        self.data = {
            'title': title,
            'body': body,
            'milestone': milestone,
            'labels': labels,
            'assignees': assignees,
            }

        # We get the issue number after submitting.
        self.github_number = None

    def submit(self, expected_number):
        """
        Execute the POST request to create a GitHub issue.

        In case of an unexpected state, go into debug mode.

        API Docs:
        https://docs.github.com/en/rest/reference/issues#create-an-issue
        """
        url = f'https://api.github.com/repos/{self.owner}/{self.repo}/issues'

        if DRY_RUN:
            print(f"Would post to {url}:\n{self.data}")
            self.github_number = expected_number
            return

        # Avoid crossing the rate limit (5000/hr).
        sleep(1)

        response = requests.post(
            url=url,
            headers={'accept': 'application/vnd.github.v3+json'},
            json=self.data,
            auth=(config.OAUTH_USER, config.OAUTH_TOKEN)
            )

        if response.status_code != 201:
            print('Error: Issue not created!')
            print(response.status_code, response.reason)
            print(response.text)
            print(response.headers)
            import pdb
            pdb.set_trace()

        # Remember the GitHub URL assigned to each ticket.
        with open('tickets_created.tsv', 'a') as f:
            github_url = response.json()['html_url']
            f.write(f'{self.trac_url()}\t{github_url}\n')

        if response.json()['number'] != expected_number:
            print(f"Expected number {expected_number}, got {github_url}")
            print(
                "Back up the Trac DB, "
                "delete the submitted tickets from the currently used copy, "
                "and try again.\n"
                "Also, the comments of this ticket will not be posted.\n"
                "Close the debugger after you found the problem."
                )
            import pdb
            pdb.set_trace()

        self.github_number = expected_number

    def trac_url(self):
        """
        Return this issue's Trac URL.
        """
        return config.TRAC_TICKET_PREFIX + str(self.t_id)

    def submitMyComments(self, comments):
        """
        Look through `comments`, and submit the ones about this ticket.

        API Docs:
        https://docs.github.com/en/rest/reference/issues#create-an-issue-comment
        """
        for comment in (c for c in comments if c['t_id'] == self.t_id):
            self._submitComment(self.commentFromTracData(comment))

    @classmethod
    def fromTracData(
            cls,
            component,
            owner,
            summary,
            description,
            priority,
            keywords,
            **kwargs):
        """
        Create a GitHubRequest from Trac ticket data fields.
        """
        return cls(
            owner=config.OWNER,
            repo=get_repo(component),
            trac_id=kwargs['t_id'],
            title=summary,
            body=get_body(description, data=kwargs),
            closed=kwargs['status'] == 'closed',
            milestone=None,
            labels=get_labels(
                component,
                priority,
                keywords,
                kwargs['status'],
                kwargs['resolution']
                ),
            assignees=get_assignees(owner),
            )

    @classmethod
    def fromTracDataMultiple(cls, trac_data):
        """
        Generate GitHubRequests from an iterable of dicts of Trac tickets.
        """
        for ticket in trac_data:
            yield cls.fromTracData(**ticket)

    @staticmethod
    def commentFromTracData(trac_data):
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
            f"{parse_body(trac_data['newvalue'])}"
            )

        return {'body': body}

    def _submitComment(self, comment_data):
        """
        Send a POST request to GitHub creating the comment from `comment_data`.
        """
        url = f'https://api.github.com/repos/' \
              f'{self.owner}/{self.repo}/issues/{self.github_number}/comments'

        if DRY_RUN:
            print(f"Would post to {url}:\n{comment_data}")
            return

        if not self.github_number:
            print(f"Trac ticket {self.t_id} did not receive a GitHub number.")
            import pdb
            pdb.set_trace()

        # Avoid crossing the rate limit (5000/hr).
        sleep(1)

        response = requests.post(
            url=url,
            headers={'accept': 'application/vnd.github.v3+json'},
            json=comment_data,
            auth=(config.OAUTH_USER, config.OAUTH_TOKEN)
            )

        if response.status_code != 201:
            print('Error: Comment not created!')
            print(response.status_code, response.reason)
            print(response.text)
            print(response.headers)
            import pdb
            pdb.set_trace()

        # Remember the GitHub URL assigned to each ticket.
        with open('comments_created.tsv', 'a') as f:
            github_url = response.json()['html_url']
            f.write(f'{self.trac_url()}\t{github_url}\n')

    def closeIfNeeded(self):
        """
        If the ticket status is closed,
        send a PATCH request to GitHub to close it.
        Unfortunately we can't directly create it as closed.

        API docs:
        https://docs.github.com/en/rest/reference/issues#update-an-issue
        """
        if not self.github_number:
            print('No GitHub number assigned. Was this issue posted?')
            import pdb
            pdb.set_trace()

        url = (
            f'https://api.github.com/repos/{self.owner}/{self.repo}/issues/'
            f'{self.github_number}'
            )

        if self.closed:
            if DRY_RUN:
                print(f"Would close issue by PATCHing: {url}")
                return

            response = requests.patch(
                url=url,
                headers={'accept': 'application/vnd.github.v3+json'},
                json={'state': 'closed'},
                auth=(config.OAUTH_USER, config.OAUTH_TOKEN)
                )
            if response.status_code != 200:
                print('Error: Issue not closed!')
                print(response.status_code, response.reason)
                print(response.text)
                print(response.headers)
                import pdb
                pdb.set_trace()


def get_body(description, data):
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
        f"T{data['t_id']} {data['t_type']} was created by {reporter}"
        f" on {showtime(data['time'])}.\n"
        f"{changed_message}"
        f"{pr_message}"
        "\n"
        f"{parse_body(description)}"
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
    Otherwise, the status is used, if it is not "assigned", "new", or "closed".
    """

    if status == 'closed' and resolution:
        return {resolution}

    if status in ['in_work', 'needs_changes', 'needs_merge', 'needs_review']:
        return {status}

    return set()


def parse_body(description):
    """
    Parses text with squiggly-bracketed or backtick-surrounded monospace.
    Converts the squiggly brackets to backtick brackets.
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
    min_squiggly = description.find('{{{')

    if is_first_index(min_squiggly, min_backtick):
        return (
            convert_issue_content(description[:min_squiggly]) +
            parse_squiggly(description[min_squiggly:])
            )

    if is_first_index(min_backtick, min_squiggly):
        return (
            convert_issue_content(description[:min_backtick]) +
            parse_backtick(description[min_backtick:])
            )

    return convert_issue_content(description)


def convert_issue_content(text):
    """
    Convert TracWiki text to GitHub Markdown.
    Ignore included images.
    """
    return convert(text, '')


def parse_squiggly(description):
    """
    Interpret squiggly brackets:

    - If a #!rst marker is the first token,
    remove the brackets and return the text inside.

    - Otherwise, convert the brackets to triple backticks.
    Leave text as is until the closing squiggly brackets,
    which are again converted to triple backticks.
    After that, let parse_body continue.
    """
    if not description.startswith('{{{'):
        raise ValueError('Desc starts with ', description[:10])
    ending = description.find('}}}') + 3
    content = description[3:ending-3]

    if content.strip().startswith('#!rst'):
        return content.split('#!rst', 1)[1] + parse_body(description[ending:])

    return '```' + content + '```' + parse_body(description[ending:])


def parse_backtick(description):
    """
    Leave text as is until the closing backtick.
    After that, let parse_body continue.
    """
    if not description.startswith('`'):
        raise ValueError('Desc starts with ', description[:10])
    description = description[1:]
    ending = description.find('`') + 1
    return '`' + description[:ending] + parse_body(description[ending:])


if __name__ == '__main__':
    main()
