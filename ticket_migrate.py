# Migrate Trac tickets to GitHub.
from config import REPOSITORY_MAPPING, FALLBACK_REPOSITORY


def get_repo(component):
    """
    Given the Trac component,
    choose the GitHub repository to create the issue in.
    """
    return REPOSITORY_MAPPING.get(component, FALLBACK_REPOSITORY)


def labels_from_component(component: str):
    """
    Given the Trac component,
    choose the labels to apply on the GitHub issue, if any.
    """
    if component in REPOSITORY_MAPPING:
        return []

    return [component]


def labels_from_keywords(keywords: str):
    """
    Given the Trac `keywords` string, clean it up and parse it into a list.
    """
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


def get_labels(component: str, priority: str, keywords: str):
    """
    Given the Trac component, priority, and keywords,
    return the labels to apply on the GitHub issue.
    """
    priority_label = 'priority-{}'.format(priority.lower())
    keyword_labels = labels_from_keywords(keywords)
    component_labels = labels_from_component(component)
    return {priority_label}.union(keyword_labels).union(component_labels)
