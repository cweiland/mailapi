from sqlalchemy.orm.exc import NoResultFound

from .domain import domain_exists
from .password import generate_md5_password
from .maildir import generate_maildir_path
from .models import Mailbox
from .helpers import parse_email_domain
from .alias import add_alias, delete_aliases
from .db import get_db_session


def create_mailbox(email_address,
                   full_name,
                   plain_password,
                   quota=0,
                   language='en_US',
                   storage_base_dir='/var/vmail',
                   storage_node='vmail1'):
    """ Creates a new mailbox

    :param email_address: String, the desired email address
    :param full_name: String, full name
    :param plain_password: String, plain text password
    :param quota: Int, # of MB
    :param language: I guess for i18n
    :param storage_base_dir: Usually /var/vmail
    :param storage_node: /var/vmail/<storage_node>
    :raises: ValueError if the given email address is invalid
    :raises: RuntimeError if the domain does not exist
    :raises: RuntimeError if the mailbox already exists
    :return: Mailbox object
    """

    # Get domain and user; Possible ValueError
    local_part, domain = parse_email_domain(email_address)

    if not domain_exists(domain):
        raise RuntimeError('Domain does not exist.')

    if mailbox_exists(email_address):
        raise RuntimeError('A mailbox with the email address %s already '
                           'exists.' % email_address)

    mailbox = Mailbox()
    mailbox.username = email_address
    mailbox.password = generate_md5_password(plain_password)
    mailbox.language = language
    mailbox.storagebasedirectory = storage_base_dir
    mailbox.storagenode = storage_node
    mailbox.maildir = generate_maildir_path(email_address)
    mailbox.quota = int(quota)
    mailbox.domain = domain
    mailbox.local_part = local_part
    mailbox.active = 1
    mailbox.name = full_name

    # Creates a self-referrential alias; Not exactly sure why, but iredadmin
    # does this
    # See: https://bitbucket.org/zhb/iredadmin-ose/src/45d6d5c30269d32d7818ea9dd1d5e0fb0d962d46/libs/mysql/user.py?at=default#cl-255 # noqa (suppresses PEP8 warning)
    add_alias(email_address, email_address)

    DBSession = get_db_session()
    DBSession.add(mailbox)
    DBSession.flush()

    return mailbox


def mailbox_exists(email_address):
    """ Determines if a mailbox with the given email address exists in the DB

    :param email_address: String
    :return: True if the mailbox exists else False
    """

    try:
        get_db_session().query(Mailbox).filter_by(username=email_address).one()
        return True
    except NoResultFound:
        return False


def delete_mailbox(email_address):
    """ Deletes the mailbox from the database by the given email address.

    :param email_address: String
    :return: True if success else False
    """

    if not mailbox_exists(email_address):
        raise RuntimeError('The given email address does not exist: %s' %
                           email_address)

    delete_aliases(email_address)
    num_deleted = get_db_session().query(Mailbox).\
        filter_by(username=email_address).delete()

    return num_deleted == 1