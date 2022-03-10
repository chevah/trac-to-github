import hashlib


def trac_hash(text):
    """
    Hash filenames and ticket IDs in the same way as Trac.
    """
    return hashlib.sha1(str(text).encode('utf-8')).hexdigest()


def get_attachment_path(root, ticket_id, filename):
    """
    Process the root location, ticket ID and filename
    into the Trac attachment path.
    """
    ticket_hash = trac_hash(ticket_id)
    return (
        root.rstrip('/') + '/' +
        ticket_hash[:3] + '/' +
        ticket_hash + '/' +
        trac_hash(filename)
        )
