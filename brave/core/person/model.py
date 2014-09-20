from mongoengine import Document, StringField, EmailField, DateTimeField, BooleanField, ReferenceField, ListField

from brave.core.character.model import EVECharacter
from brave.core.account.model import User
from brave.core.key.model import EVECredential
from brave.core.util.field import IPAddressField

log = __import__('logging').getLogger(__name__)


class Person(Document):
    meta = dict(
        collection = 'People',
        allow_inheritance = False,
        indexes = [''],
    )

    # Fields holding the various components of the Person. NEVER modify these directly.
    _characters = ListField(ReferenceField(EVECharacter), db_field='c', default=list)
    _users = ListField(ReferenceField(User), db_field='u', default=list)
    _keys = ListField(ReferenceField(EVECredential), db_field='k', default=list)
    _ips = ListField(IPAddressField, db_field='i', default=list)
    _history = ListField(PersonEvent, db_field='h', default=list)

    @property
    def complexity(self):
        """A simple measure of the number of items that constitute the Person. This is used
        to determine which Person should be the base when merging 2 Persons into one."""
        return len(self.history)

    def add_component(self, type, reason, component):
        """Abstract method for adding a component to this Person."""
        field = getattr(self, "_" + type + "s")
        log.info("ADDED {0} {1} to Person {2} due to {3}".format(type, self.component_repr(type, component), self.id, reason))
        # TODO: Create PersonEvent here
        field.append(component)
        self.save()

    def remove_component(self, type, reason, component):
        """Abstract method for removing a component from this Person."""
        field = getattr(self, "_" + type + "s")
        if not component in field:
            log.info("Attempt to remove {0} {1} from Person {2} failed: Not found".format(type, self.component_repr(type, component), self.id))
            return False
        log.info("REMOVED {0} {1} from Person {2} due to {3}".format(type, self.component_repr(type, component), self.id, reason))
        # TODO: Create PersonEvent here
        field.remove(component)
        self.save()

    def add_character(self, reason, character):
        self.add_component("character", reason, character)

    def add_user(self, reason, user):
        self.add_component("user", reason, user)

    def add_key(self, reason, key):
        self.add_component("key", reason, key)

    def add_ip(self, reason, ip):
        self.add_component("ip", reason, ip)

    def remove_character(self, reason, character):
        self.remove_component("character", reason, character)

    def remove_user(self, reason, user):
        self.remove_component("user", reason, user)

    def remove_key(self, reason, key):
        self.remove_component("key", reason, key)

    def remove_ip(self, reason, ip):
        self.remove_component("ip", reason, ip)

    @staticmethod
    def component_repr(type, component):
        """Returns the primary identification of the component."""
        if type == "character":
            return component.name
        elif type == "user":
            return component.username
        elif type == "key":
            return component.key
        elif type == "ip":
            return component
        else:
            return None