from mongoengine import Document, ListField, StringField

class User(Document):
    meta = dict(
        collection = 'Users',
        allow_inheritance = False,
        indexes = ['otp'],
    )

    username = StringField(db_field='u', required=True, unique=True, regex=r'[a-z][a-z0-9_.-]+')
    otp = ListField(StringField(), default=list)

def remove_otps(dry_run=True):
    """Remove OTPs from all users. Mainly intended to serve as a 'migration' from the old single
    OTP setup before the addition of TOTPs changed the way OTPs were handled in the User model."""
    for u in User.objects:
        if u.otp:
            print u.username
            if not dry_run:
                u.otp = None
                u.rotp = None
                u.save()