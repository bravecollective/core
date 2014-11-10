from mongoengine import EmbeddedDocument, EmbeddedDocumentField, Document, StringField, DateTimeField, BooleanField, ReferenceField, ListField
from brave.core.person.model import Person, PersonEvent
from brave.core.account.model import User
from brave.core.application.model import Application
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

    # Stores the app for app and subapp bans.
    app = ReferenceField(Application, db_field='a')

    # Determines the area that a user is banned from for subapp bans. Unused otherwise.
    subarea = StringField(db_field='a')

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

    # Permissions
    CREATE_GLOBAL_PERM = 'core.ban.create.global'
    CREATE_SERVICE_PERM = 'core.ban.create.service'
    CREATE_APP_PERM = 'core.ban.create.app.{app_short}'
    CREATE_SUBAPP_PERM = 'core.ban.create.subapp.{app_short}.{subapp_id}'
    LOCK_GLOBAL_PERM = 'core.ban.lock.global'
    LOCK_SERVICE_PERM = 'core.ban.lock.service'
    LOCK_APP_PERM = 'core.ban.lock.app.{app_short}'
    LOCK_SUBAPP_PERM = 'core.ban.lock.subapp.{app_short}.{subapp_id}'
    UNLOCK_GLOBAL_PERM = 'core.ban.unlock.global'
    UNLOCK_SERVICE_PERM = 'core.ban.unlock.service'
    UNLOCK_APP_PERM = 'core.ban.unlock.app.{app_short}'
    UNLOCK_SUBAPP_PERM = 'core.ban.unlock.app.{app_short}.{subapp_id}'
    ENABLE_GLOBAL_PERM = 'core.ban.enable.global'
    ENABLE_SERVICE_PERM = 'core.ban.enable.service'
    ENABLE_APP_PERM = 'core.ban.enable.app.{app_short}'
    ENABLE_SUBAPP_PERM = 'core.ban.enable.subapp.{app_short}.{subapp_id}'
    DISABLE_GLOBAL_PERM = 'core.ban.disable.global'
    DISABLE_SERVICE_PERM = 'core.ban.disable.service'
    DISABLE_APP_PERM = 'core.ban.disable.app.{app_short}'
    DISABLE_SUBAPP_PERM = 'core.ban.disable.subapp.{app_short}.{subapp_id}'
    COMMENT_GLOBAL_PERM = 'core.ban.comment.global'
    COMMENT_SERVICE_PERM = 'core.ban.comment.service'
    COMMENT_APP_PERM = 'core.ban.comment.app.{app_short}'
    COMMENT_SUBAPP_PERM = 'core.ban.comment.subapp.{app_short}.{subapp_id}'
    MODIFY_REASON_GLOBAL_PERM = 'core.ban.modify_reason.global'
    MODIFY_REASON_SERVICE_PERM = 'core.ban.modify_reason.service'
    MODIFY_REASON_APP_PERM = 'core.ban.modify_reason.app.{app_short}'
    MODIFY_REASON_SUBAPP_PERM = 'core.ban.modify_reason.subapp.{app_short}.{subapp_id}'
    VIEW_SECRET_REASON_GLOBAL_PERM = 'core.ban.view_secret_reason.global'
    VIEW_SECRET_REASON_SERVICE_PERM = 'core.ban.view_secret_reason.service'
    VIEW_SECRET_REASON_APP_PERM = 'core.ban.view_secret_reason.app.{app_short}'
    VIEW_SECRET_REASON_SUBAPP_PERM = 'core.ban.view_secret_reason.subapp.{app_short}.{subapp_id}'
    MODIFY_SECRET_REASON_GLOBAL_PERM = 'core.ban.modify_secret_reason.global'
    MODIFY_SECRET_REASON_SERVICE_PERM = 'core.ban.modify_secret_reason.service'
    MODIFY_SECRET_REASON_APP_PERM = 'core.ban.modify_secret_reason.app.{app_short}'
    MODIFY_SECRET_REASON_SUBAPP_PERM = 'core.ban.modify_secret_reason.subapp.{app_short}.{subapp_id}'
    MODIFY_LOCKED_GLOBAL_PERM = 'core.ban.modify_locked.global'
    MODIFY_LOCKED_SERVICE_PERM = 'core.ban.modify_locked.service'
    MODIFY_LOCKED_APP_PERM = 'core.ban.modify_locked.app.{app_short}'
    MODIFY_LOCKED_SUBAPP_PERM = 'core.ban.modify_locked.subapp.{app_short}.{subapp_id}'

    @property
    def create_perm(self):
        return self.get_perm("CREATE")

    @property
    def lock_perm(self):
        return self.get_perm("LOCK")

    @property
    def unlock_perm(self):
        return self.get_perm("UNLOCK")

    @property
    def enable_perm(self):
        return self.get_perm("ENABLE")

    @property
    def disable_perm(self):
        return self.get_perm("DISABLE")

    @property
    def comment_perm(self):
        return self.get_perm("COMMENT")

    @property
    def modify_reason_perm(self):
        return self.get_perm("MODIFY_REASON")

    @property
    def view_secret_reason_perm(self):
        return self.get_perm("VIEW_SECRET_REASON")

    @property
    def modify_secret_reason_perm(self):
        return self.get_perm("MODIFY_SECRET_REASON")

    @property
    def modify_locked_perm(self):
        return self.get_perm("MODIFY_LOCKED")

    def get_perm(self, action):
        perm = getattr(self, action + "_" + self.ban_type.upper() + "_BAN")
        if self.ban_type == "app" or self.ban_type == "subapp":
            perm = perm.format(app_short=self.app.short)
        if self.ban_type == "subapp":
            perm = perm.format(subapp_id=self.subarea)

        return perm

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
