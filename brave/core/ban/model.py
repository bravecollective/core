from mongoengine import EmbeddedDocument, EmbeddedDocumentField, Document, StringField, DateTimeField, BooleanField, ReferenceField, ListField, ValidationError
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

    banner = ReferenceField(User, db_field='b', required=True)
    created = DateTimeField(db_field='c', required=True)
    # Note: We don't use Mongoengine expireasafterseconds because we want to retain copies of bans after they expire.
    # An expiration of None means that the ban is permanent.
    expires = DateTimeField(db_field='d')

    # Determines what the ban prevents the banned from doing.
    # Subapp bans are for banning from individual areas of an app, such as a chat room in Jabber
    ban_type = StringField(db_field='bt', choices=["global", "service", "app", "subapp"], required=True)

    # Stores the app for app and subapp bans.
    app = ReferenceField(Application, db_field='a')

    # Determines the area that a user is banned from for subapp bans. Unused otherwise.
    subarea = StringField(db_field='s')

    # The reason for the ban. This will be publicly available.
    reason = StringField(db_field='r', required=True)
    # The secret reason, for when the banner doesn't want the actual reason for the ban to be public.
    secret_reason = StringField(db_field='sr')

    # Allows for the banner (and others) to comment on the ban with additional details.
    history = ListField(EmbeddedDocumentField('BanHistory'), db_field='h')

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
    VIEW_GLOBAL_PERM = 'core.ban.view.global'
    VIEW_SERVICE_PERM = 'core.ban.view.service'
    VIEW_APP_PERM = 'core.ban.view.app.{app_short}'
    VIEW_SUBAPP_PERM = 'core.ban.view.app.{app_short}.{subapp_id}'
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
    UNBANNABLE_PERM = 'core.ban.unbannable'

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

    @property
    def view_perm(self):
        return self.get_perm("VIEW")

    def get_perm(self, action):
        perm = getattr(self, action + "_" + self.ban_type.upper() + "_PERM")
        if self.ban_type == "app":
            perm = perm.format(app_short=self.app.short)
        if self.ban_type == "subapp":
            perm = perm.format(app_short=self.app.short, subapp_id=self.subarea)

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
        self.save()
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
        log.info("{0} changed reason from '{1}' to '{2}'".format(user.username, self.reason, reason))
        self.reason = reason
        self.save()
        return True

    def modify_secret_reason(self, user, reason):
        self.history.append(ModifySecretReasonHistory(user=user, prev_reason=self.secret_reason, new_reason=reason))
        log.info("{0} changed secret reason from '{1}' to '{2}'".format(user.username, self.secret_reason, reason))
        self.secret_reason = reason
        self.save()
        return True

    def modify_type(self, user, type, app=None, subarea=None):

        if type == "app" and not app:
            return False

        if type == "subapp" and (not app or not subarea):
            return False

        if type == "app" or type == "subapp":
            app = Application.objects(short=app).first()
            if not app:
                return False

        prev_app = self.app.short if self.ban_type == "app" or self.ban_type == "subapp" else None
        prev_subarea = self.subarea if self.ban_type == "subarea" else None
        new_app = app.short if type == "app" or type == "subapp" else None
        new_subarea = subarea if type == "subapp" else None

        self.history.append(ModifyTypeBanHistory(user=user, prev_type=self.ban_type, new_type=type,
                                                 prev_app=prev_app, prev_subarea=prev_subarea, new_app=new_app,
                                                 new_subarea=new_subarea))
        log.info("{0} changed type from '{1}' to '{2}'".format(user.username, self.ban_type, type))

        self.app = Application.objects(short=new_app).first()
        self.subarea = new_subarea
        self.ban_type = type
        self.save()
        return True

    def clean(self):
        """Mongoengine pre-save validation \o/
        We opt to throw an error for extraneous information here instead of just purging it because the history files
        will be created with the (incorrect) extraneous information even if we purge it from the ban itself on save."""

        if self.ban_type == "global" or self.ban_type == "service":
            if self.app or self.subarea:
                raise ValidationError("Global and Service bans don't have apps or subareas.")

        if self.ban_type == "app":
            if not self.app:
                raise ValidationError("App bans require that an app be specified")
            if self.subarea:
                raise ValidationError("App bans don't have subareas")

        if self.ban_type == "subapp":
            if not self.app or not self.subarea:
                raise ValidationError("Subapp bans require that an app and subarea be specified")

        if not self.created:
            self.created = datetime.utcnow()

    @property
    def permanent(self):
        return False if self.duration else True

    @property
    def duration(self):
        return None if not self.expires else self.expires.replace(tzinfo=None) - self.created.replace(tzinfo=None)

    @property
    def enabled(self):
        if self._enabled and (not self.expires or self.expires.replace(tzinfo=None) > datetime.utcnow()):
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

    @staticmethod
    def create(banner, duration, ban_type, reason, banned_ident, person, app=None, subarea=None, secret_reason=None, banned_type="character"):
        ban = PersonBan(banner=banner, ban_type=ban_type, reason=reason,
                        orig_person=str(person.id), app=app, subarea=subarea,secret_reason=secret_reason, banned_type=banned_type, banned_ident=banned_ident)
        ban.created = datetime.utcnow()
        ban.expires = ban.created + duration if duration else None
        ban.history.append(CreateBanHistory(user=banner))
        return ban.save()

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
    meta = dict(
        allow_inheritance = True,
    )

    user = ReferenceField(User)
    time = DateTimeField()

    def display(self):
        return None

    def clean(self):
        """For some reason using default=datetime.utcnow() for time was not working as intended..."""
        if not self.time:
            self.time = datetime.utcnow()

    def __repr__(self):
        return str(type(self)) + "(" + self.display() + ")"

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
        return "Changed reason from '{0}' to '{1}'".format(self.prev_reason, self.new_reason)

class ModifySecretReasonHistory(BanHistory):
    prev_reason = StringField()
    new_reason = StringField()
    def display(self):
        return "Changed secret reason from '{0}' to '{1}'".format(self.prev_reason, self.new_reason)

class ModifyTypeBanHistory(BanHistory):
    prev_type = StringField()
    new_type = StringField()
    prev_app = StringField()
    prev_subarea = StringField()
    new_app = StringField()
    new_subarea = StringField()
    def display(self):
        prev = self.prev_type.upper()
        if prev == "APP" or prev == "SUBAPP":
            prev += ": {0}".format(self.prev_app)
        if prev.startswith("SUBAPP"):
            prev += "({0})".format(self.prev_subarea)
        new = self.new_type.upper()
        if new == "APP" or new == "SUBAPP":
            new += ": {0}".format(self.new_app)
        if new.startswith("SUBAPP"):
            new += "({0})".format(self.new_subarea)
        return "Changed type from {0} to {1}".format(prev, new)
