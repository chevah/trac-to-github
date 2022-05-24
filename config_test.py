# Trac User to GitHub user mapping.
# This is the configuration used by the test suite.

USER_MAPPING = {
    'adi': ('adiroiban', 'Adi Roiban <adi.roiban@chevah.com>'),
    'danuker': ('danuker', 'Dan Haiduc <danuthaiduc@gmail.com>'),
    'Adi Roiban': ('adiroiban', 'Adi Roiban <adi.roiban@chevah.com>'),
    }

# GitHub User to GitHub UID mapping (for avatar purposes).
UID_MAPPING = {
    'adiroiban': 204609,
    'mthuurne': 246676,
    }

# Users that are allowed by GitHub
# to be assignees of issues in the target repositories.
ASSIGNABLE_USERS = {
    'adiroiban',
    }

TRAC_TICKET_PREFIX = 'https://trac.chevah.com/ticket/'

# GitHub repository for Trac tickets.
REPOSITORY = 'trac-migration-staging'

# Owner of GitHub repositories where to create issues.
OWNER = 'chevah'

# The root URL of the attachment files, containing the ticket/ and wiki/ dirs.
ATTACHMENT_ROOT = 'https://site.com/trunk/'

# The user to create the issues through the API.
# Create a token with `repo` permissions here:
# https://github.com/settings/tokens
OAUTH_USER = 'danuker'
OAUTH_TOKEN = 'ghp_qwertyuiop'

ALLOWED_EMAILS = {
    'allowed@example.com',
    }
