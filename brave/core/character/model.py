# character/model.py

# encoding: utf-8

from __future__ import unicode_literals

from collections import OrderedDict
from datetime import datetime

from brave.core.helper import get_membership
from mongoengine import Document, StringField, DateTimeField, ReferenceField, \
    IntField, BooleanField, FloatField, ListField, NULLIFY, PULL
from brave.core.util.signal import update_modified_timestamp
from brave.core.key.model import EVECredential
from brave.core.util import evelink
from brave.core.permission.model import Permission, WildcardPermission
from brave.core.application.model import Application

log = __import__('logging').getLogger(__name__)


@update_modified_timestamp.signal
class EVEEntity(Document):
    meta = dict(
        allow_inheritance=True,
        indexes=[
            'identifier'
        ],
        # TODO: migrate and rename collection
    )

    identifier = IntField(db_field='i', unique=True)
    name = StringField(db_field='n')

    modified = DateTimeField(db_field='m', default=datetime.utcnow)

    @classmethod
    def get(cls, query=None, **kw):
        if query.isnumeric():
            kw['identifier'] = query
        else:
            kw['name'] = query

        try:
            return cls.objects.get(**kw)
        except cls.DoesNotExist:
            return None

    def __repr__(self):
        return '{0}({1}, {2}, "{3}")'.format(self.__class__.__name__, self.id,
                                             self.identifier, self.name)

    def __unicode__(self):
        return self.name


class EVEAlliance(EVEEntity):
    short = StringField(db_field='s')
    members = IntField(db_field='e')

    founded = DateTimeField(db_field='f')

    executor = ReferenceField('EVECorporation', db_field='x')

    @property
    def corporations(self):
        return EVECorporation.objects(alliance=self)

    @property
    def characters(self):
        return EVECharacter.objects(alliance=self)

    @classmethod
    def populate(cls):
        log.info("Populating alliances (and minimal corporate information) "
                 "from AllianceList.")

        results, a, b, c, d = None, 0, 0, 0, 0
        eve = evelink.eve.EVE()
        try:
            results = eve.alliances().result
        except:
            log.exception("Failed call.")
            results = None

        if not results:
            log.error("Unable to retrieve AllianceList.")
            return

        for b, row in enumerate(results.values()):
            log.info("Synchronizing Alliance %d: %s", row['id'], row['name'])
            record, created = EVEAlliance.objects.get_or_create(
                identifier=row['id'],
            )

            if created:
                a += 1

            record.name = row['name']
            record.short = row['ticker']
            record.founded = datetime.fromtimestamp(row['timestamp'])
            members = row['member_count']
            record = record.save()

            executor = row['executor_id']

            try:
                mapping = eve.character_names_from_ids(
                    row['member_corps'].keys()).result
            except:
                log.exception("Failed to get full mapping.  Falling back.")
                mapping = None

            for corp in row['member_corps'].values():
                log.info("Synchronizing corporation: %d", corp['id'])
                corporation, created = EVECorporation.objects.get_or_create(
                    identifier=corp['id'],
                )

                d += 1
                if created:
                    c += 1

                if mapping:
                    corporation.name = mapping[corp['id']]
                elif not corporation.name:
                    try:
                        result = eve.character_name_from_id(corp['id']).result
                        corporation.name = result['name']
                    except:
                        log.exception("Unable to get corporation name for %d.",
                                      corp['id'])
                        continue

                corporation.alliance = record
                corporation.joined = datetime.fromtimestamp(corp['timestamp'])
                corporation.save()

                if corporation.identifier == executor:
                    record.executor = corporation
                    record.save()

        log.info(
            "Population complete, %d/%d alliances, "
            "%d/%d corporations created/updated.",
            a, b, c, d)


class EVECorporation(EVEEntity):
    _short = StringField(db_field='s')
    members = IntField(db_field='e')

    founded = DateTimeField(db_field='f')

    alliance = ReferenceField(EVEAlliance)  # TODO: migrate and rename
    joined = DateTimeField(db_field='j')  # date joined alliance

    @property
    def characters(self):
        return EVECharacter.objects(corporation=self)

    @property
    def short(self):
        if not self._short:
            corp = evelink.corp.Corp(evelink.api.API())
            result = corp.corporation_sheet(self.identifier).result
            self._short = result['ticker']
            EVECorporation.objects(identifier=self.identifier).update(
                set___short=self._short)
        return self._short

    @short.setter
    def short(self, short):
        self._short = short


class EVECharacter(EVEEntity):
    meta = dict(
        indexes=[
            'owner',
        ],
    )

    alliance = ReferenceField(EVEAlliance)
    corporation = ReferenceField(EVECorporation)

    race = StringField(db_field='ra')
    bloodline = StringField(db_field='bl')
    ancestry = StringField(db_field='an')
    gender = StringField(db_field='g')
    security = FloatField(db_field='sec')

    titles = ListField(StringField(), db_field='ti', default=list)
    roles = ListField(StringField(), db_field='ro', default=list)
    personal_permissions = ListField(ReferenceField(Permission), db_field='p',
                                     default=list)

    credentials = ListField(
        ReferenceField(EVECredential, reverse_delete_rule=PULL), db_field='e',
        default=list)

    owner = ReferenceField('User', db_field='o', reverse_delete_rule=NULLIFY)

    _permissions_cache = dict()

    # Permissions
    VIEW_PERM = 'core.character.view.{character_id}'
    LIST_PERM = 'core.character.list.all'

    # DEPRECATED
    @property
    def tags(self):
        from brave.core.group.model import Group
        mapping = dict()

        for group in Group.objects:
            if group.evaluate(self.owner, self):
                mapping[group.id] = group

        def titlesort(i):
            return mapping[i].title

        return OrderedDict(
            (i, mapping[i]) for i in sorted(mapping.keys(), key=titlesort))

    @property
    def groups(self):
        """Returns the groups a character is in."""

        from brave.core.group.model import Group

        char_groups = set()

        for group in Group.objects:
            bef = datetime.utcnow()
            res = group.evaluate(self.owner, self)
            aft = datetime.utcnow()
            # print "Evaluation for group {0} took {1}".format(
            #     group.id, aft-bef)
            if res:
                char_groups.add(group)

        return char_groups

    @property
    def person(self):
        if self.owner:
            return self.owner.person

        from brave.core.person.model import Person

        person = Person.objects(_characters=self).first()

        if person:
            return person

        person = Person()
        # Ensure that the person has an id before adding a component.
        person.save()
        person.add_component((self, "create"), self)
        return person.save()

    def permissions(self, app=None, groups_cache=None):
        """Return all permissions that the character has that start with core
        or app. An app of None returns all of the character's permissions."""

        # Use a set so we don't need to worry about characters having
        # a permission from multiple groups.
        permissions = set()

        # Allow app to be either the short name or the
        # application object itself.
        if isinstance(app, Application):
            app = app.short + '.'

        # Ensure the provided string ends with a . to prevent pulling
        # permissions from another application with the same starting letters
        # (forums should not return forums2's permissions.)
        if app and app[-1] != '.':
            app = app + '.'

        # make sure we are not re-evaluating character permissions
        app_check = app
        if app_check is None:
            app_check = '_None.'

        # save time re-evalutating groups
        if groups_cache is not None:
            groups = groups_cache
        else:
            bef = datetime.utcnow()
            groups = self.groups
            aft = datetime.utcnow()
            print "Groups eval for character {0} took {1}".format(self.name,
                                                                  aft - bef)

        # Return permissions from groups that this character has.
        for group in groups:
            gbef = datetime.utcnow()
            perms = group.permissions
            gaft = datetime.utcnow()
            # print "Pulling group permissions for"
            #       "group {0} took {1}".format(group.id, gaft-gbef)
            for perm in perms:
                # Append all of the group's permissions
                # when no app is specified.
                if not app:
                    permissions.add(perm)
                    continue

                # Permissions are case-sensitive.
                if perm.id.startswith('core') or perm.id.startswith(app):
                    permissions.add(perm)

        # Return permissions that have been assigned directly to this user.
        for perm in self.personal_permissions:
            # Append all of the user's individual permissions
            # when no app is specified.
            if not app:
                permissions.add(perm)
                continue

            # If an app is specified, return only Core permissions
            # and permissions for that app.
            if perm.id.startswith('core') or perm.id.startswith(app):
                permissions.add(perm)

        # Save Permissions list in memory cache
        permissions = list(permissions)
        permissions.sort()

        return permissions

    def permissions_tags(self, application=None, groups_cache=None):
        """Returns just the string for the permissions
        owned by this character."""

        perms = self.permissions(application, groups_cache)
        permissions = list()

        for p in perms:
            permissions.append(p.id)

        return permissions

    def has_permission(self, permission):
        """Accepts both Permission objects and Strings."""

        from brave.core.group.model import Permission

        if isinstance(permission, Permission):
            permission = permission.id

        bef = datetime.utcnow()
        permissions = self.permissions()
        aft = datetime.utcnow()
        print "Permissions loading took {} ms".format(aft - bef)

        rbef = datetime.utcnow()
        res = Permission.set_grants_permission(permissions, permission)
        raft = datetime.utcnow()
        print "Set grants permission took {} ms".format(raft - rbef)

        return res

    def has_any_permission(self, permission):
        """Returns true if the character has a permission that
        would be granted by permission."""
        p = WildcardPermission.objects(id=permission)
        if len(p):
            p = p.first()
        else:
            p = WildcardPermission(id=permission)
        for permID in self.permissions():
            if p.grants_permission(permID.id):
                return True

        return False

    @property
    def has_verified_key(self):
        for k in self.credentials:
            if k.verified:
                return k

    def credential_for(self, mask):
        """Return the least-permissive API key that
        can satisfy the given mask."""

        candidates = [i for i in self.credentials if
                      not mask or not i.mask or i.mask.has_access(mask)]

        lowest = None
        lowest_count = None
        for candidate in candidates:
            bc = candidate.mask.number_of_functions()
            if lowest_count is None or bc < lowest_count:
                lowest, lowest_count = candidate, bc

        return lowest

    def credential_multi_for(self, masks):
        """Returns the lowest permission API key that
        can satisfy the highest possible given mask."""

        for mask in masks:
            if self.credential_for(mask):
                return mask, self.credential_for(mask)

        return None, None

    def delete(self):
        """Deletes the character. This is not recommended for typical use."""

        if self.owner:
            self.detach()

        super(EVECharacter, self).delete()

    def detach(self):
        """Removes all references to this character that imply ownership
        of the character."""
        if not self.owner:
            return

        # If this character is the primary character for the account,
        # wipe that field for the user.
        if self.owner:
            if self == self.owner.primary:
                self.owner.primary = None
                self.owner.save()

            # Delete any application grants associated with the character.
            for grant in self.owner.grants:
                if self in grant.characters:
                    grant.remove_character(self)

            self.owner = None

        self.save()

    @property
    def view_perm(self):
        return self.VIEW_PERM.format(character_id=str(self.id))

    @classmethod
    def pull_character(cls, name):
        """Pulls public information about this character from the EVE API,
        and adds them to the Character Collection.
        This is important for when we need to manipulate a character who
        doesn't have an API key in Core, such as banning."""

        from brave.core.util import evelink
        el = evelink.eve.EVE()

        print "Running character API update for char: {0}".format(name)

        id = 0
        try:
            # load up the pre-existing character
            char = cls.objects(name=name).first()
            id = char.identifier
        except:
            # make a new character class
            char = cls()
            id = el.character_id_from_name(name).result

        # Character doesn't exist
        if id == 0:
            return False

        info = el.character_info_from_id(id).result

        char.identifier = id
        char.corporation, char.alliance = get_membership(info)
        char.name = info['name'] if 'name' in info else info['characterName']
        if not isinstance(char.name, basestring):
            char.name = str(char.name)
        char.race = info['race'] if 'race' in info else None
        char.bloodline = (info['bloodLine'] if 'bloodLine' in info
                          else info['bloodline'] if 'bloodline' in info
                          else None)
        char.ancestry = info['ancestry'] if 'ancestry' in info else None
        char.gender = info['gender'] if 'gender' in info else None
        char.security = info['sec_status'] if 'sec_status' in info else None
        char.titles = [EVECredential.strip_tags(i.titleName) for i in info[
            'corporationTitles']] if 'corporationTitles' in info else []

        char.save()

        return char
