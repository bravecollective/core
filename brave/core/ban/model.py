from mongoengine import Document, StringField, EmailField, DateTimeField, BooleanField, ReferenceField, ListField
from brave.core.person.model import Person, PersonEvent
from brave.core.character.model import EVECharacter
from datetime import datetime, timedelta

log = __import__('logging').getLogger(__name__)


class Ban(Document):
    meta = dict(
        collection = 'Bans',
        allow_inheritance = True,
        indexes = ['person'],
    )

    banner = ReferenceField(EVECharacter, db_field='b')
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
    comments = ListField(StringField, db_field='c')

    # Allows for admins to lock the Ban, making it unmodifiable. Comments can still be added while locked.
    locked = BooleanField(db_field='l', default=False)

    # Used to disable bans prior to their expiration.
    _enabled = BooleanField(db_field='e', default=True)

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
