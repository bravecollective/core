from mongoengine import EmbeddedDocument, EmbeddedDocumentField, Document, StringField, DateTimeField, BooleanField, ReferenceField, ListField
from brave.core.person.model import Person, PersonEvent
from brave.core.account.model import User
from datetime import datetime, timedelta

log = __import__('logging').getLogger(__name__)


class Ban(Document):
    meta = dict(
        collection = 'Bans',
        allow_inheritance = True,
        indexes = [],
    )

    banner = ReferenceField(User, db_field='b')
    created = DateTimeField(default=datetime.utcnow(), db_field='c', required=True)
    # Note: We don't use Mongoengine expireasafterseconds because we want to retain copies of bans after they expire.
    # A duration of None means that the ban is permanent.
    duration = DateTimeField(db_field='d')

    # Determines what the ban prevents the banned from doing.
    # Subapp bans are for banning from individual areas of an app, such as a chat room in Jabber
    ban_type = StringField(db_field='bt', choices=["global", "service", "app", "subapp"])

    # Determines the areas that a user is banned from for subapp bans. Unused otherwise.
    subareas = StringField(db_field='a')

    # The reason for the ban. This will be publicly available.
    reason = StringField(db_field='r', required=True)
    # The secret reason, for when the banner doesn't want the actual reason for the ban to be public.
    secret_reason = StringField(db_field='sr')

    # Allows for the banner (and others) to comment on the ban with additional details.
    history = ListField(EmbeddedDocumentField(BanHistory), db_field='c')

    # Allows for admins to lock the Ban, making it unmodifiable to non-Admins. Comments can still be added while locked.
    locked = BooleanField(db_field='l', default=False)

    # Used to disable bans prior to their expiration.
    _enabled = BooleanField(db_field='e', default=True)

    def enable(self, user):
        if not self._enabled:
            self._enabled = True
            self.history.append(EnableBanHistory(user=user))
            log.info("{0} enabled ban {1}".format(user.username, self.id))
            self.save()
            return True

        return False

    def disable(self, user):
        if self._enabled:
            self._enabled = False
            self.history.append(DisableBanHistory(user=user))
            log.info("{0} disabled ban {1}".format(user.username, self.id))
            self.save()
            return True

        return False

    def comment(self, user, comment):
        self.history.append(CommentHistory(user=user, comment=comment))
        log.info("{0} commented {1} on ban {2}".format(user.username, comment, self.id))
        return True

    def lock(self, user):
        if not self.locked:
            self.locked = True
            self.history.append(LockBanHistory(user=user))
            log.info("{0} locked ban {1}".format(user.username, self.id))
            self.save()
            return True

        return False

    def unlock(self, user):
        if self.locked:
            self.locked = False
            self.history.append(UnlockBanHistory(user=user))
            log.info("{0} unlocked ban {1}".format(user.username, self.id))
            self.save()
            return True

        return False

    def modify_reason(self, user, reason):
        self.history.append(ModifyReasonHistory(user=user, prev_reason=self.reason, new_reason=reason))
        self.reason = reason
        self.save()
        return True

    def modify_secret_reason(self, user, reason):
        self.history.append(ModifySecretReasonHistory(user=user, prev_reason=self.reason, new_reason=reason))
        self.secret_reason = reason
        self.save()
        return True

    @property
    def permanent(self):
        return False if self.duration else True

    @property
    def enabled(self):
        if self._enabled and not self.created or (self.created + timedelta(self.duration) > datetime.utcnow()):
            return True

        return False


class PersonBan(Ban):
    """This Ban class is for Bans that apply to a single Person."""

    # Stores the ObjectID of the person this event happened to, We store it as a string rather
    # than as a reference for when a Person are deleted during a merge.
    orig_person = StringField(db_field='p', required=True)

    # Records the actual banned entity
    banned_type = StringField(db_field='t', choices=["character", "user", "ip", "key", "person"])
    banned_ident = StringField(db_field='i')

    @property
    def person(self):
        """The Person that this ban describes currently. Can be different than orig_person, in the event that the person
        the event originally described was merged into another person."""
        person = Person.objects(id=self.orig_person)
        if person:
            return person.first()

        person_merge = PersonEvent.objects(target_ident=self.orig_person).first()
        return person_merge.current_person

class BanHistory(EmbeddedDocument):
    user = ReferenceField(User)
    time = DateTimeField(default=datetime.utcnow())

    def display(self):
        return None

    def __repr__(self):
        return "{0}({1})".format(type(self), self.display)

class CreateBanHistory(BanHistory):
    def display(self):
        return "Created Ban"

class DisableBanHistory(BanHistory):
    def display(self):
        return "Disabled Ban"

class EnableBanHistory(BanHistory):
    def display(self):
        return "Enabled Ban"

class CommentHistory(BanHistory):
    comment =  StringField(required=True)
    def display(self):
        return self.comment

class LockBanHistory(BanHistory):
    def display(self):
        return "Locked Ban"

class UnlockBanHistory(BanHistory):
    def display(self):
        return "Unlocked Ban"

class ModifyReasonHistory(BanHistory):
    prev_reason = StringField()
    new_reason = StringField()
    def display(self):
        return "Changed reason from {0} to {1}".format(self.prev_reason, self.new_reason)

class ModifySecretReasonHistory(BanHistory):
    prev_reason = StringField()
    new_reason = StringField()
    def display(self):
        return "Changed secret reason from {0} to {1}".format(self.prev_reason, self.new_reason)
