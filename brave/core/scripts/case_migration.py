from __future__ import print_function, unicode_literals

from mongoengine.errors import OperationError, ValidationError

from brave.core.account.model import User
from brave.core.util.script_init import script_init

def migrate():
    failures = []
    for u in User.objects():
        try:
            u.username = u.username.lower()
            u.email = u.email.lower()
            u.save()
        except Exception as e:
            print("Exception when operating on {}: {}".format(u, e))
            failures.append(u)
    return failures

def main():
    script_init()
    migrate()

if __name__ == "__main__":
    main()
