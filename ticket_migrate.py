# Migrate Trac tickets to GitHub.
from collections import deque

import requests
import sqlite3
import sys
from time import sleep
from typing import Union

import config

# Set to False to perform actual GitHub issue creation.
DRY_RUN = True


def convert_issue_content(text: str):
    """
    Convert the description of a Trac issue to GitHub flavored Markdown.
    """
    return text


def get_repo(component):
    """
    Given the Trac component,
    choose the GitHub repository to create the issue in.
    """
    return config.REPOSITORY_MAPPING.get(component, config.FALLBACK_REPOSITORY)


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

    keywords = [typo_fixes.get(kw, kw) for kw in keywords]
    discarded = [kw for kw in keywords if kw not in allowed_keyword_labels]

    if discarded:
        print("Warning: discarded keywords:", discarded)

    return {kw for kw in keywords if kw in allowed_keyword_labels}


def get_labels(component: str, priority: Union[str, None], keywords: str):
    """
    Given the Trac component, priority, and keywords,
    return the labels to apply on the GitHub issue.
    """
    priority_label = labels_from_priority(priority)
    keyword_labels = labels_from_keywords(keywords)
    component_labels = labels_from_component(component)
    labels = {priority_label}.union(keyword_labels).union(component_labels)
    return sorted(labels)


def labels_from_priority(priority):
    """
    Interpret None (missing) priority as Low.
    """
    if priority is None:
        return 'priority-low'
    return 'priority-{}'.format(priority.lower())


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


def parse_squiggly(description):
    """
    Convert the squiggly brackets to triple backticks.
    Leave text as is until the closing squiggly brackets.
    After that, let parse_body continue.
    """
    if not description.startswith('{{{'):
        raise ValueError('Desc starts with ', description[:10])
    ending = description.find('}}}') + 3
    return (
        '```' +
        description[3:ending-3] +
        '```' + parse_body(description[ending:])
        )


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


def get_body(description, data):
    reporters = get_assignees(data['reporter'])
    if reporters:
        reporter = reporters[0]
    else:
        reporter = data['reporter']

    body = (
        f"T{data['t_id']} {data['t_type']} was created by {reporter}.\n"
        "\n"
        f"{parse_body(description)}"
        )

    return body


class GitHubRequest:
    """
    A plain object holding all data needed for creating a GitHub issue.
    """
    def __init__(self, owner, repo, title, body, milestone, labels, assignees):
        self.owner = owner
        self.repo = repo
        self.data = {
            'title': title,
            'body': body,
            'milestone': milestone,
            'labels': labels,
            'assignees': assignees,
            }

    def submit(self):
        """
        Execute the POST request to create a GitHub issue.
        """
        url = f'https://api.github.com/repos/{self.owner}/{self.repo}/issues'

        if DRY_RUN:
            print(f"Would post to {url}:\n{self.data}")
        else:
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

            print(self.data['t_id'], response.json()['html_url'])

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
            title=summary,
            body=get_body(description, data=kwargs),
            milestone=None,
            labels=get_labels(component, priority, keywords),
            assignees=get_assignees(owner),
            )

    @classmethod
    def fromTracDataMultiple(cls, trac_data):
        """
        Generate GitHubRequests from an iterable of dicts of Trac tickets.
        """
        for ticket in trac_data:
            yield cls.fromTracData(**ticket)


class NumberPredictor:
    """
    A best-effort algorithm to preserve issue IDs (named "numbers" in the API).
    """
    def __init__(self):
        """
        Store an index of next issue/PR numbers per repository.
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

        if DRY_RUN:
            raise AssertionError(f"Would request GitHub issues for {repo}.")

        issues = requests.get(
            url=f'https://api.github.com/repos/{config.OWNER}/{repo}/issues',
            headers={'accept': 'application/vnd.github.v3+json'},
            auth=(config.OAUTH_USER, config.OAUTH_TOKEN),
            params={'state': 'all'},
            )
        last_issue_number = issues.json()[0]['number']

        pulls = requests.get(
            url=f'https://api.github.com/repos/{config.OWNER}/{repo}/pulls',
            headers={'accept': 'application/vnd.github.v3+json'},
            auth=(config.OAUTH_USER, config.OAUTH_TOKEN),
            params={'state': 'all'},
            )
        last_pull_number = pulls.json()[0]['number']

        next_number = max(last_issue_number, last_pull_number) + 1
        print(f"Next issue for {repo} will be {next_number}.")

        return next_number

    def orderTickets(self, tickets):
        """
        Choose an order to create tickets on GitHub so that we maximize
        matches of GitHub IDs with Trac IDs.
        """
        repositories = (
            list(config.REPOSITORY_MAPPING.values()) +
            [config.FALLBACK_REPOSITORY]
            )
        for repo in set(repositories):
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

        return ordered_tickets


def select_open_tickets(tickets):
    """
    Choose only tickets which don't have a closed status.
    """
    for t in tickets:
        if t['status'] != 'closed':
            yield t


def select_tickets_for_repo(tickets, repo: str):
    """
    From a list of Trac tickets,
    select the ones that will be posted to a given GitHub repository.
    """
    return [t for t in tickets if get_repo(t['component']) == repo]


def read_trac_tickets():
    """
    Read the Trac ticket data, and generate dicts.
    """
    if len(sys.argv) != 2:
        print("Need to pass the path to Trac DB as argument.")
        sys.exit(1)

    db = sqlite3.connect(sys.argv[1])
    for row in db.execute('SELECT * FROM ticket ORDER BY id'):
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
            keywords
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
            }


def main():
    """
    Read the Trac DB and post the open tickets to GitHub.
    """
    tickets = list(select_open_tickets(read_trac_tickets()))

    np = NumberPredictor()
    tickets = np.orderTickets(tickets)

    for issue in GitHubRequest.fromTracDataMultiple(tickets):
        issue.submit()


if __name__ == '__main__':
    main()
