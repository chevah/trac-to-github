import unittest

import config_test
import link_issues as li

# Monkeypatch the SUT to use the test config.
li.config = config_test


class TestCommentRequest(unittest.TestCase):
    """
    `CommentRequest` objects are created from Trac data.
    """
    def test_commentJSON(self):
        """
        Creates a comment JSON fit for GitHub, mentioning the GH PR in a link.
        """
        sut = li.CommentRequest(
            trac_id='123',
            repo='server',
            github_number='1',
            pr_link='https://github.com/chevah/server/pull/234',
            )

        self.assertEqual(
            'PR for trac-123 is at https://github.com/chevah/server/pull/234.',
            sut.commentText()
            )

    def test_fromTracDataMultiple(self):
        """
        The CommentRequest object is created
        with data from the submission history
        and only the PR link (`branch`) is retrieved from the Trac DB.
        """

        requests = li.CommentRequest.fromTracDataMultiple(
            trac_data=[
                {
                    't_id': 123,
                    'branch': 'https://github.com/chevah/server/pull/234',
                    'component': 'misleading',
                    }
                ],
            ticket_mapping={
                123: 'https://github.com/chevah/server/issues/5454',
                }
            )
        requests = list(requests)
        self.assertEqual(1, len(requests))

        sut = requests[0]

        self.assertEqual(
            'PR for trac-123 is at https://github.com/chevah/server/pull/234.',
            sut.commentText()
            )

        self.assertEqual(
            'https://api.github.com/repos/chevah/server/issues/5454/comments',
            sut.commentsURL()
            )


if __name__ == '__main__':
    unittest.main()
