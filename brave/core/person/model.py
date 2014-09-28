from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, EmailField, DateTimeField, BooleanField, ReferenceField, ListField
from datetime import datetime

from brave.core.character.model import EVECharacter
from brave.core.account.model import User
from brave.core.key.model import EVECredential
from brave.core.util.field import IPAddressField
from brave.core.person.util import get_type, object_repr

log = __import__('logging').getLogger(__name__)


class Person(Document):
    meta = dict(
        collection='People',
        allow_inheritance=False,
        indexes=['_users','_characters'],
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
        return len(self._history)

    def add_component(self, reason, component):
        """Abstract method for adding a component to this Person."""

        comp_type = get_type(component)

        field = getattr(self, "_" + comp_type + "s")
        match, reason_string = reason
        log.info("ADDED {0} {1} to Person {2} due to {3}".format(comp_type, object_repr(component), self.id, reason_string))

        pe = PersonEvent(person=self.id, action='add', reason=reason_string)
        pe.match = match
        pe.target = component
        pe.save()

        self._history.append(pe)
        field.append(component)
        self.save()

        return True

    def remove_component(self, reason, component):
        """Abstract method for removing a component from this Person."""

        comp_type = get_type(component)

        field = getattr(self, "_" + comp_type + "s")
        if not component in field:
            log.info("Attempt to remove {0} {1} from Person {2} failed: Not found".format(comp_type, object_repr(component), self.id))
            return False
        match, reason_string = reason
        log.info("REMOVED {0} {1} from Person {2} due to {3}".format(comp_type, object_repr(component), self.id, reason_string))

        pe = PersonEvent(person=self.id, action='remove', reason=reason_string)
        pe.match = match
        pe.target = component
        pe.save()

        self._history.append(pe)
        field.remove(component)
        self.save()

        return True


class PersonEvent(Document):
    meta = dict(
        allow_inheritance=False,
        indexes=['person']
    )

    # Stores the ObjectID of the person this event happened to, We store it as a string rather
    # than as a reference for when Person's are deleted during a merge.
    person = StringField(db_field='p')

    # The type of the component that is being added or removed from the Person
    target_type = StringField(db_field='t', choices=["character", "user", "ip", "key", "person"])
    # The component that is being added or removed
    target_ident = StringField(db_field='g')
    # Whether to add or remove the target
    action = StringField(db_field='a', choices=["add", "remove", "merge"])
    time = DateTimeField(db_field='u', default=datetime.utcnow())

    # The identifier of the object that led to the creation of this event
    match_ident = StringField(db_field='mn')
    # The type of the object that led to the creation of this event
    match_type = StringField(db_field='mt', choices=["character", "user", "ip", "key", "person"])
    # The reason that the match led to this event
    reason = StringField(db_field='mr', choices=["create", "component_match"])

    @property
    def target(self):
        if self.target_type == "character":
            return EVECharacter.objects(name=self.target_ident).first()
        elif self.target_type == "user":
            return User.objects(username=self.target_ident).first()
        elif self.target_type == "ip":
            return self.target_ident
        elif self.target_type == "key":
            return EVECredential.objects(key=self.target_ident).first()
        elif self.target_type == "person":
            return Person.objects(id=self.target_ident).first()

        return None

    @target.setter
    def target(self, target):
        self.target_ident = object_repr(target)
        self.target_type = get_type(target)

    @property
    def match(self):
        if self.match_type == "character":
            return EVECharacter.objects(name=self.match_ident).first()
        elif self.match_type == "user":
            return User.objects(username=self.match_ident).first()
        elif self.match_type == "ip":
            return self.match_ident
        elif self.match_type == "key":
            return EVECredential.objects(key=self.match_ident).first()
        elif self.match_type == "person":
            return Person.objects(id=self.match_ident).first()

        return None

    @match.setter
    def match(self, match):
        self.match_ident = object_repr(match)
        self.match_type = get_type(match)

