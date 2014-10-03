from brave.core.account.model import User

def remove_otps(dry_run=True):
    """Remove OTPs from all users. Mainly intended to serve as a 'migration' from the old single
    OTP setup before the addition of TOTPs changed the way OTPs were handled in the User model."""
    for u in User.objects:
        if u.otp:
            print u.username
            if not dry_run:
                u.otp = None
                u.save()