from __future__ import print_function, unicode_literals

from mongoengine.errors import OperationError

from brave.core.account.model import User
from brave.core.scripts import script_init

def migrate_usernames():
    for u in User.objects():
        try:
            u.username = u.username.lower()
            u.save()
        except OperationError:
            print("username collision! {}".format(u))

def migrate_emails():
    for u in User.objects():
        try:
            u.email = u.email.lower()
            u.save()
        except OperationError:
            print("username collision! {}".format(u))

def main():
    script_init()
    migrate_usernames()
    migrate_emails()

if __name__ == "__main__":
    main()
