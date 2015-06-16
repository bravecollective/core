from __future__ import unicode_literals

from itertools import chain
from datetime import datetime, timedelta
from mongoengine import Document, StringField, EmailField, DateTimeField, BooleanField, ReferenceField, ListField
from mongoengine.fields import LongField

from brave.core.util.signal import update_modified_timestamp
from brave.core.util.field import PasswordField, IPAddressField

from web.core import config

log = __import__('logging').getLogger(__name__)


@update_modified_timestamp.signal
class User(Document):
    meta = dict(
        collection='Users',
        allow_inheritance=False,
        indexes=['otp'],
    )

    # Field Definitions

    username = StringField(db_field='u', required=True, unique=True, regex=r'[a-z][a-z0-9_.-]+')
    email = EmailField(db_field='e', required=True, unique=True, regex=r'[^A-Z]+')  # disallow uppercase characters
    password = PasswordField(db_field='p')
    active = BooleanField(db_field='a', default=False)
    confirmed = DateTimeField(db_field='c')
    admin = BooleanField(db_field='d', default=False)

    # TODO: Extract into a sub-document and re-name the DB fields.
    rotp = BooleanField(default=False)
    otp = ListField(StringField(max_length=12), default=list)

    primary = ReferenceField('EVECharacter')  # "Default" character to use during authz.

    modified = DateTimeField(db_field='m', default=datetime.utcnow)
    seen = DateTimeField(db_field='s')
    host = IPAddressField(db_field='h')

    # Distinguish how we identified the other core accounts as being owned by this one
    # because IP address IDing can cause mis-IDs
    other_accs_char_key = ListField(ReferenceField('User'), db_field='otherAccountsCharKey')
    other_accs_IP = ListField(ReferenceField('User'), db_field='otherAccountsIP')

    _permission_cache = list()

    # Permissions
    VIEW_PERM = 'core.account.view.{account_id}'

    # Python Magic Methods

    def __repr__(self):
        return 'User({0}, {1})'.format(self.id, self.username).encode('ascii', 'backslashreplace')

    def __unicode__(self):
        return self.username

    @property
    def created(self):
        return self.id.generation_time

    # Related Data Lookups

    @property
    def credentials(self):
        from brave.core.key.model import EVECredential

        return EVECredential.objects(owner=self)

    @property
    def characters(self):
        from brave.core.character.model import EVECharacter

        return EVECharacter.objects(owner=self)

    @property
    def grants(self):
        from brave.core.application.model import ApplicationGrant

        return ApplicationGrant.objects(user=self)

    @property
    def attempts(self):
        return LoginHistory.objects(user=self)

    @property
    def recovery_keys(self):
        return PasswordRecovery.objects(user=self)

    @property
    def otp_required(self):
        return self.rotp and len(self.otp)

    @property
    def person(self):
        from brave.core.person.model import Person

        person = Person.objects(_users=self).first()

        if person:
            return person

        person = Person()
        # Ensure that the person has an id before adding a component.
        person.save()
        person.add_component((self, "create"), self)
        return person.save()

    # Functions to manage YubiKey OTP

    def addOTP(self, yid):
        yid = yid[:12]
        if yid in self.otp:
            return False
        self.otp.append(yid)
        self.save()
        return True

    def removeOTP(self, yid):
        yid = yid[:12]
        if not yid in self.otp:
            return False
        self.otp.remove(yid)
        self.save()
        return True

    def merge(self, other):
        """Consumes other and takes its children."""

        other.credentials.update(set__owner=self)
        other.characters.update(set__owner=self)

        LoginHistory.objects(user=other).update(set__user=self)

        from brave.core.group.model import Group
        from brave.core.application.model import Application, ApplicationGrant

        Group.objects(creator=other).update(set__creator=self)
        Application.objects(owner=other).update(set__owner=self)
        ApplicationGrant.objects(user=other).update(set__user=self)

        other.delete()

    def delete(self):

        for c in self.characters:
            c.detach()

        self.credentials.delete()
        self.grants.delete()
        self.attempts.delete()
        self.recovery_keys.delete()

        dups = set(self.other_accs_char_key)

        for other in dups:
            self.remove_duplicate(self, other)

        dups = set(self.other_accs_IP)

        for other in dups:
            self.remove_duplicate(self, other, IP=True)

        super(User, self).delete()

    @property
    def primary_permissions(self):
        """Returns all permissions that any character this user owns has."""

        perms = set()

        if not self.primary:
            return perms

        bef = datetime.utcnow()
        per = self.primary.permissions()
        aft = datetime.utcnow()
        print "Primary Character {0} permissions took {1}".format(self.primary.name, aft - bef)
        for p in per:
            perms.add(p)

        print "-----"
        perms = list(perms)
        perms.sort(key=lambda p: p.id)

        return perms

    @property
    def permissions(self):
        """Returns all permissions that any character this user owns has."""

        perms = set()

        for c in self.characters:
            bef = datetime.utcnow()
            per = c.permissions()
            aft = datetime.utcnow()
            print "Character {0} permissions took {1}".format(c.name, aft - bef)
            for p in per:
                perms.add(p)

        print "-----"
        perms = list(perms)
        perms.sort(key=lambda p: p.id)

        return perms

    def has_permission(self, permission):
        """Accepts both Permission objects and Strings. Returns the first character found with that permission,
           preferring the user's primary character."""

        from brave.core.group.model import Permission

        if isinstance(permission, Permission):
            permission = permission.id

        log.debug('Checking if user has permission {0}'.format(permission))

        bef = datetime.utcnow()
        primary_perms = self.primary_permissions
        aft = datetime.utcnow()
        print "Primary Character Permissions took {}".format(aft - bef)

        rbef = datetime.utcnow()
        res = Permission.set_grants_permission(primary_perms, permission)
        raft = datetime.utcnow()
        print "SET GRANTS PERM took {}".format(raft - rbef)

        if res:
            return res;
        else:

            log.debug('PRIMARY CHARACTER DOES NOT HAVE PERMISSION, CHECKING OTHER CHARACTERS {0}'.format(permission))

            bef = datetime.utcnow()
            perms = self.permissions
            aft = datetime.utcnow()
            print "Permissions took {}".format(aft - bef)

            rbef = datetime.utcnow()
            res = Permission.set_grants_permission(perms, permission)
            raft = datetime.utcnow()
            print "SET GRANTS PERM took {}".format(raft - rbef)

            return res

    def has_any_permission(self, permission):
        """Returns true if the character has a permission that would be granted by permission."""
        from brave.core.permission.model import WildcardPermission

        p = WildcardPermission.objects(id=permission)
        if len(p):
            p = p.first()
        else:
            p = WildcardPermission(id=permission)
        for permID in self.permissions:
            if p.grants_permission(permID.id):
                return True
            if permID.grants_permission(p.id):
                return True

        return False

    @staticmethod
    def add_duplicate(acc, other, IP=False):
        """Marks other as a duplicate account to this account.
        And marks this account as duplicate to other."""

        # If the 2 accounts supplied are the same, do nothing
        if acc.id == other.id:
            return

        if not IP:
            if other not in acc.other_accs_char_key:
                acc.other_accs_char_key.append(other)
            if acc not in other.other_accs_char_key:
                other.other_accs_char_key.append(acc)
        else:
            if other not in acc.other_accs_IP:
                acc.other_accs_IP.append(other)
            if acc not in other.other_accs_IP:
                other.other_accs_IP.append(acc)

        acc.save()
        other.save()

    @staticmethod
    def remove_duplicate(acc, other, IP=False):
        """Removes a duplicate account connection for both accounts."""

        # If the 2 accounts supplied are the same, do nothing
        if acc.id == other.id:
            return

        if not IP:
            if other in acc.other_accs_char_key:
                acc.other_accs_char_key.remove(other)
            if acc in other.other_accs_char_key:
                other.other_accs_char_key.remove(acc)
        else:
            if other in acc.other_accs_IP:
                acc.other_accs_IP.remove(other)
            if acc in other.other_accs_IP:
                other.other_accs_IP.remove(acc)

        acc.save()
        other.save()

    @property
    def view_perm(self):
        """Returns the permission required to view this user's account details."""
        return self.VIEW_PERM.format(account_id=str(self.id))


class LoginHistory(Document):
    meta = dict(
        collection="AuthHistory",
        allow_inheritance=False,
        indexes=[
            'user',
            # Automatically delete records as they expire.
            dict(fields=['expires'], expireAfterSeconds=0)
        ]
    )

    user = ReferenceField(User)
    success = BooleanField(db_field='s', default=True)
    location = IPAddressField(db_field='l')
    # Will throw an exception if the config has a non integer config value
    expires = DateTimeField(db_field='e',
                            default=lambda: datetime.utcnow() + timedelta(days=int(config['core.login_history_days'])))

    def __repr__(self):
        return 'LoginHistory({0}, {1}, {2}, {3})'.format(
            self.id.generation_time.isoformat(),
            'PASS' if self.success else 'FAIL',
            self.user.username,
            self.location
        )


class PasswordRecovery(Document):
    meta = dict(
        collection="PwdRecovery",
        allow_inheritance=False,
        indexes=[
            'user',
            # Automatically delete records as they expire.
            dict(fields=['expires'], expireAfterSeconds=0)
        ]
    )

    user = ReferenceField(User, required=True)
    recovery_key = LongField(db_field='k', required=True)
    expires = DateTimeField(db_field='e', default=lambda: datetime.utcnow() + timedelta(minutes=15))

    @property
    def created(self):
        return self.id.generation_time

    def __repr__(self):
        return 'PasswordRecovery({0}, {1}, {2})'.format(
            self.id.generation_time.isoformat(),
            self.user.username,
            self.recovery_key
        )
