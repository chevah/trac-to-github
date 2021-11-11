# Trac User to GitHub user mapping.
# This is the configuration used by the test suite.

USER_MAPPING = {
    'adi': ('adiroiban', 'Adi Roiban <adi.roiban@chevah.com>'),
    'danuker': ('danuker', 'Dan Haiduc <danuthaiduc@gmail.com>'),
    }

TRAC_TICKET_PREFIX = 'https://trac.chevah.com/ticket/'

# Trac ticket Component to GitHub repository mapping.
REPOSITORY_MAPPING = {
    'client': 'client',
    'commons': 'commons',
    'trac-migration-staging': 'trac-migration-staging',
    }

# GitHub repository for Trac tickets with Component not in the mapping.
FALLBACK_REPOSITORY = 'server'

# Owner of GitHub repositories where to create issues.
OWNER = 'chevah'

# The user to create the issues through the API.
# Create a token with `repo` permissions here:
# https://github.com/settings/tokens
OAUTH_USER = 'danuker'
OAUTH_TOKEN = 'ghp_qwertyuiop'
