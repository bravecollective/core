# encoding: utf-8

from __future__ import unicode_literals

from collections import OrderedDict
from datetime import datetime
from mongoengine import Document, StringField, DateTimeField, ReferenceField, IntField, BooleanField, FloatField, ListField, NULLIFY, PULL
from brave.core.util.signal import update_modified_timestamp
from brave.core.key.model import EVECredential
from brave.core.util.eve import api
from brave.core.permission.model import Permission, WildcardPermission
from brave.core.application.model import Application


log = __import__('logging').getLogger(__name__)


@update_modified_timestamp.signal
class EVEEntity(Document):
    meta = dict(
            allow_inheritance = True,
            indexes = [
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
        return '{0}({1}, {2}, "{3}")'.format(self.__class__.__name__, self.id, self.identifier, self.name)
    
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
        log.info("Populating alliances (and minimal corporate information) from AllianceList.")
        
        results, a, b, c, d = None, 0, 0, 0, 0
        
        try:
            results = api.eve.AllianceList()
        except:
            log.exception("Failed call.")
            results = None
        
        if not results or not results.get('row', []):
            log.error("Unable to retrieve AllianceList.")
            return
        
        for b, row in enumerate(results.row):
            log.info("Synchronizing Alliance %d: %s", row.allianceID, row.name)
            record, created = EVEAlliance.objects.get_or_create(
                    identifier = row.allianceID,
                )
            
            if created: a += 1
            
            record.name = row.name
            record.short = str(row.shortName)
            record.founded = datetime.strptime(row.startDate, "%Y-%m-%d %H:%M:%S")
            members = row.memberCount
            record = record.save()
            
            executor = row.executorCorpID
            
            try:
                result = api.eve.CharacterName(ids=','.join([str(i.corporationID) for i in row.memberCorporations.row]))
                mapping = {int(i.characterID): str(i.name) for i in result.row}
            except:
                log.exception("Failed to get full mapping.  Falling back.")
                mapping = None
            
            for row in row.memberCorporations.row:
                log.info("Synchronizing corporation: %d", row.corporationID)
                corporation, created = EVECorporation.objects.get_or_create(
                        identifier = row.corporationID,
                    )
                
                d += 1
                if created: c += 1
                
                if mapping:
                    corporation.name = mapping[row.corporationID]
                elif not corporation.name:
                    try:
                        result = api.eve.CharacterName(ids=str(row.corporationID))
                        corporation.name = str(result.row[0].name)
                    except:
                        log.exception("Unable to get corporation name for %d.", row.corporationID)
                        continue
                
                corporation.alliance = record
                corporation.joined = datetime.strptime(row.startDate, "%Y-%m-%d %H:%M:%S")
                corporation.save()
                
                if corporation.identifier == executor:
                    record.executor = corporation
                    record.save()
        
        log.info("Population complete, %d/%d alliances, %d/%d corporations created/updated.", a, b, c, d)


class EVECorporation(EVEEntity):
    short = StringField(db_field='s')
    members = IntField(db_field='e')
    
    founded = DateTimeField(db_field='f')
    
    alliance = ReferenceField(EVEAlliance)  # TODO: migrate and rename
    joined = DateTimeField(db_field='j')  # date joined alliance
    
    @property
    def characters(self):
        return EVECharacter.objects(corporation=self)


class EVECharacter(EVEEntity):
    meta = dict(
            indexes = [
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
    personal_permissions = ListField(ReferenceField(Permission), db_field='p', default=list)
    
    credentials = ListField(ReferenceField(EVECredential, reverse_delete_rule=PULL), db_field='e', default=list)
    
    owner = ReferenceField('User', db_field='o', reverse_delete_rule=NULLIFY)
    
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
        
        return OrderedDict((i, mapping[i]) for i in sorted(mapping.keys(), key=titlesort))
        
    @property
    def groups(self):
        """Returns the groups a character is in."""
        
        from brave.core.group.model import Group
        
        char_groups = set()
        
        for group in Group.objects:
            if group.evaluate(self.owner, self):
                char_groups.add(group)
                
        return char_groups
    
    def permissions(self, app=None):
        """Return all permissions that the character has that start with core or app.
           An app of None returns all of the character's permissions."""
        
        # Use a set so we don't need to worry about characters having a permission from multiple groups.
        permissions = set()
        
        # Allow app to be either the short name or the application object itself.
        if isinstance(app, Application):
            app = app.short + '.'
        
        # Ensure the provided string ends with a . to prevent pulling permissions from another application with the
        # same starting letters (forums should not return forums2's permissions.)
        if app and app[-1] != '.':
            app = app + '.'
        
        # Return permissions from groups that this character has.
        for group in self.groups:
            for perm in group.permissions:
                # Append all of the group's permissions when no app is specified.
                if not app:
                    permissions.add(perm)
                    continue
                
                # Permissions are case-sensitive.
                if perm.id.startswith('core') or perm.id.startswith(app):
                    permissions.add(perm)
        
        # Return permissions that have been assigned directly to this user.
        for perm in self.personal_permissions:
            # Append all of the user's individual permissions when no app is specified.
            if not app:
                permissions.add(perm)
                continue
            
            # If an app is specified, return only Core permissions and permissions for that app.
            if perm.id.startswith('core') or perm.id.startswith(app):
                permissions.add(perm)
                
        # Evaluate all of the User's wildcard permissions.
        for perm in permissions.copy():
            if not isinstance(perm, WildcardPermission):
                continue
            
            permissions |= perm.get_permissions()
        
        return permissions
        
    def permissions_tags(self, application=None):
        """Returns just the string for the permissions owned by this character."""
        
        perms = self.permissions(application)
        permissions = list()
        
        for p in perms:
            permissions.append(p.id)
            
        return permissions
        
    def has_permission(self, permission):
        """Accepts both Permission objects and Strings."""
        
        from brave.core.group.model import Permission
        
        if isinstance(permission, str) or isinstance(permission, unicode):
            perm_id = permission
            permission = Permission.objects(id=perm_id)
            
            if not permission:
                log.info("Permission %s not found.", perm_id)
                
                # The permission specified was not found in the database, so we loop through the character's
                # permissions and see if they would grant this permission. Might be worth optimizing in the future
                # by adding a new EVECharacter function that returns only that character's wildcard permissions.
                for p in self.permissions():
                    if p.grants_permission(perm_id):
                        return True
                
                return False
            
            permission = permission.first()
        
        return(permission in self.permissions())
    
    @property
    def has_verified_key(self):
        for k in self.credentials:
            if k.verified:
                return k
    
    def credential_for(self, mask):
        """Return the least-permissive API key that can satisfy the given mask."""
        
        candidates = [i for i in self.credentials if not mask or not i.mask or i.mask.has_access(mask)]
        
        lowest = None
        lowest_count = None
        for candidate in candidates:
            bc = candidate.mask.number_of_functions()
            if lowest_count is None or bc < lowest_count:
                lowest, lowest_count = candidate, bc
                
        return lowest
        
    def credential_multi_for(self, masks):
        """Returns the lowest permission API key that can satisfy the highest possible given mask."""
        
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
        """Removes all references to this character that imply ownership of the character."""
        if not self.owner:
            return
        
        # If this character is the primary character for the account, wipe that field for the user.
        if self == self.owner.primary:
            self.owner.primary = None
            self.owner.save()
                    
        # Delete any application grants associated with the character.
        for grant in self.owner.grants:
            if self == grant.character:
                grant.delete()
        
        self.owner = None
        self.save()
    
    @property
    def view_perm(self):
        return self.VIEW_PERM.format(character_id=str(self.id))
