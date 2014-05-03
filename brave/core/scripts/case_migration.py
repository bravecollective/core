from __future__ import print_function, unicode_literals

import sys

from brave.core import core_loadapp
if __name__ == "__main__":
    core_loadapp("config:"+sys.argv[1] if len(sys.argv) > 1 else None)

from mongoengine.errors import OperationError, ValidationError

from brave.core.account.model import User

def ensure_lowercase(u, field):
    if u[field] != u[field].lower():
        try:
            updated = User.objects(id=u.id, **{field:u[field]}).update_one(
                    **{'set__'+field: u[field].lower()})
            if not updated:
                print("failure updating {} (raced user?): {}".format(field, u))
                return False
        except OperationError:
            print("collision updating {}: {}".format(field, u))
            return False
    return True

def migrate():
    failures = []
    for u in User.objects():
        username_success = ensure_lowercase(u, 'username')
        email_success = ensure_lowercase(u, 'email')
        if not username_success or not email_success:
            failures.append(u)
    return failures

def main():
    migrate()

if __name__ == "__main__":
    main()
