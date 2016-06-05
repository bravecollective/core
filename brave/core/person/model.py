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
    _ips = ListField(IPAddressField(), db_field='i', default=list)
    _history = ListField(ReferenceField("PersonEvent"), db_field='h', default=list)

    @property
    def complexity(self):
        """A simple measure of the number of items that constitute the Person. This is used
        to determine which Person should be the base when merging 2 Persons into one."""
        return len(self._history)

    def add_component(self, reason, component, suppress_events=False):
        """Abstract method for adding a component to this Person."""

        comp_type = get_type(component)

        field = getattr(self, "_" + comp_type + "s")
        match, reason_string = reason

        if component in field:
            log.info("Attempt to add {0} {1} from Person {2} failed: Already exists".format(comp_type, object_repr(component), self.id))
            self.check_for_conflicts()
            return False

        log.info("ADDED {0} {1} to Person {2} due to {3}".format(comp_type, object_repr(component), self.id, reason_string))

        if not suppress_events:
            pe = PersonEvent(person=str(self.id), action='add', reason=reason_string)
            pe.match = match
            pe.target = component
            pe.save()

            self._history.append(pe)
        field.append(component)
        setattr(self, "_" + comp_type + "s", field)
        self.save()

        self.check_for_conflicts()

        return True

    def remove_component(self, reason, component, suppress_events=False):
        """Abstract method for removing a component from this Person."""

        comp_type = get_type(component)

        field = getattr(self, "_" + comp_type + "s")
        if not component in field:
            log.info("Attempt to remove {0} {1} from Person {2} failed: Not found".format(comp_type, object_repr(component), self.id))
            self.check_for_conflicts()
            return False
        match, reason_string = reason
        log.info("REMOVED {0} {1} from Person {2} due to {3}".format(comp_type, object_repr(component), self.id, reason_string))

        if not suppress_events:
            pe = PersonEvent(person=str(self.id), action='remove', reason=reason_string)
            pe.match = match
            pe.target = component
            pe.save()

            self._history.append(pe)
        field.remove(component)
        setattr(self, "_" + comp_type + "s", field)
        self.save()

        self.check_for_conflicts()

        return True

    def check_for_conflicts(self, check_ip=False):
        """Checks for conflicts between this Person and every other person."""
        for c in self._characters:
            people = Person.objects(_characters=c)
            if len(people) > 1:
                Person.merge(people[0], people[1], (c, "component_match"))

        for u in self._users:
            people = Person.objects(_users=u)
            if len(people) > 1:
                Person.merge(people[0], people[1], (u, "component_match"))

        for k in self._keys:
            people = Person.objects(_keys=k)
            if len(people) > 1:
                Person.merge(people[0], people[1], (k, "component_match"))

        if check_ip:
            for i in self._ips:
                people = Person.objects(_ips=i)
                if len(people) > 1:
                    Person.merge(people[0], people[1], (i, "component_match"))

    @staticmethod
    def merge(person1, person2, reason, suppress_events=False):
        """Merges person1 and person2 into one person."""
        match, reason_string = reason
        person = person1 if person1.complexity >= person2.complexity else person2
        tbd_person = person2 if person1.complexity >= person2.complexity else person1

        log.info("MERGING {0} into {1} due to {2} of {3}".format(tbd_person, person, reason_string, object_repr(match)))

        if not suppress_events:
            pe = PersonEvent(person=str(person.id), action='merge', reason=reason_string)
            pe.match = match
            pe.target = tbd_person
            pe.save()

        for c in tbd_person._characters:
            if c in person._characters:
                continue
            person._characters.append(c)

        for u in tbd_person._users:
            if u in person._users:
                continue
            person._users.append(u)

        for k in tbd_person._keys:
            if k in person._keys:
                continue
            person._keys.append(k)

        for i in tbd_person._ips:
            if i in person._ips:
                continue
            person._ips.append(i)

        if not suppress_events:
            person._history = PersonEvent.history_merge(person._history, tbd_person._history)

        person.save()
        tbd_person.delete()

    @property
    def bans(self):

        from brave.core.ban.model import PersonBan

        bans = []
        for b in PersonBan.objects:
            if b.person == self:
                bans.append(b)

        return bans

    def banned(self, app=None, subarea=None):
        bans = self.bans
        for b in bans:
            if not b.enabled:
                continue

            if b.ban_type == "global":
                return b

            if app:
                if b.ban_type == "service":
                    return b

                if b.ban_type == "app" and b.app.short == app:
                    return b

                if subarea:
                    if b.ban_type == "subapp" and b.app.short == app and b.subarea == subarea:
                        return b

        return False


    def __repr__(self):
        return "Person({e.id}, users={e._users}, characters={e._characters}, keys={e._characters}, ips={e._ips})".format(e=self)


class PersonEvent(Document):
    meta = dict(
        allow_inheritance=False,
        indexes=['person']
    )

    # Stores the ObjectID of the person this event happened to, We store it as a string rather
    # than as a reference for when a Person are deleted during a merge.
    person = StringField(db_field='p', required=True)

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
    reason = StringField(db_field='mr', choices=["create", "component_match", "user_add"])

    @property
    def current_person(self):
        """The Person that this event describes currently. Can be different than person, in the event that the person
        the event originally described was merged into another person."""
        person = Person.objects(id=self.person)
        if person:
            return person.first()

        person_merge = PersonEvent.objects(target_ident=self.person).first()
        return person_merge.current_person

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

    @staticmethod
    def history_merge(history1, history2):
        """We assume that history1 and history2 are already sorted by time."""
        x_index = y_index = 0
        merged_list = []
        while(x_index < len(history1) or y_index < len(history2)):
            if x_index >= len(history1):
                merged_list.append(history2[y_index])
                y_index += 1
                continue
            elif y_index >= len(history2):
                merged_list.append(history1[x_index])
                x_index += 1
                continue

            if history1[x_index].time > history2[y_index].time:
                merged_list.append(history1[x_index])
                x_index += 1
                continue
            else:
                merged_list.append(history2[y_index])
                y_index += 1
                continue

        return merged_list

    def __repr__(self):
        return "PersonEvent({e.id}, action={e.action}, person={e.person}".format(e=self)




