# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime
from mongoengine import Document, StringField, DateTimeField, BooleanField, ReferenceField, IntField
from mongoengine.errors import NotUniqueError
from marrow.util.bunch import Bunch

from brave.core.util import strip_tags
from brave.core.util.signal import update_modified_timestamp, trigger_api_validation
from brave.core.util.eve import api


log = __import__('logging').getLogger(__name__)


@trigger_api_validation.signal
@update_modified_timestamp.signal
class EVECredential(Document):
    meta = dict(
            collection = "Credentials",
            allow_inheritance = False,
            indexes = [
                    'owner',
                    # Don't keep expired credentials.
                    dict(fields=['expires'], expireAfterSeconds=0)
                ],
        )
    
    key = IntField(db_field='k')
    code = StringField(db_field='c')
    kind = StringField(db_field='t')
    mask = IntField(db_field='a', default=0)
    verified = BooleanField(db_field='v', default=False)
    expires = DateTimeField(db_field='e')
    owner = ReferenceField('User', db_field='o', reverse_delete_rule='CASCADE')
    
    modified = DateTimeField(db_field='m', default=datetime.utcnow)
    
    def __repr__(self):
        return 'EVECredential({0}, {1}, {2}, {3!r})'.format(self.id, self.kind, self.mask, self.owner)
    
    @property
    def characters(self):
        from brave.core.character.model import EVECharacter
        return EVECharacter.objects(credentials=self)
    
    # EVE API Integration

    def pull_character(self, info):
        """This always updates all information on the character, so that we do not end up with
        inconsistencies. There is some weirdness that, if a user already has a key with full
        permissions, and adds a limited one, we'll erase information on that character. We should
        probably check for and refresh info from the most-permissioned key instead of this."""
        from brave.core.character.model import EVEAlliance, EVECorporation, EVECharacter
        try:
            char = EVECharacter(identifier=info.characterID).save()
        except NotUniqueError:
            char = EVECharacter.objects(identifier=info.characterID)[0]

        if self.mask & 8:
            info = api.char.CharacterSheet(self, characterID=info.characterID)
        elif self.mask & 8388608:
            info = api.eve.CharacterInfo(self, characterID=info.characterID)

        char.corporation, char.alliance = self.get_membership(info)

        char.name = info.name
        char.owner = self.owner
        if self not in char.credentials:
            char.credentials.append(self)
        char.race = info.race if 'race' in info else None
        char.bloodline = (info.bloodLine if 'bloodLine' in info
                          else info.bloodline if 'bloodline' in info
                          else None)
        char.ancestry = info.ancestry if 'ancestry' in info else None
        char.gender = info.gender if 'gender' in info else None
        char.security = info.security if 'security' in info else None
        char.titles = [strip_tags(i.titleName) for i in info.corporationTitles.row] if 'corporationTitles' in info else []
        char.roles = [i.roleName for i in info.corporationRoles.row] if 'corporationRoles' in info else []

        char.save()
    
    def get_membership(self, info):
        from brave.core.character.model import EVEAlliance, EVECorporation, EVECharacter
        
        # This is a stupid edge-case to cover inconsistency between API calls.
        allianceName = info.alliance if 'alliance' in info else (info.allianceName if 'allianceName' in info else None)
        corporationName = info.corporation if 'corporation' in info else info.corporationName
        
        alliance, created = EVEAlliance.objects.get_or_create(
                identifier = info.allianceID,
                defaults = dict(name=allianceName)
            ) if 'allianceID' in info and info.allianceID else (None, False)
        
        if alliance and not created and alliance.name != allianceName:
            alliance.name = allianceName
            alliance = alliance.save()
            
        corporation, created = EVECorporation.objects.get_or_create(
                identifier = info.corporationID,
                defaults = dict(name=corporationName, alliance=alliance)
            )
        
        if corporation.name != corporationName:
            corporation.name = corporationName
        
        if alliance and corporation.alliance != alliance:
            corporation.alliance = alliance
        
        elif not alliance and corporation.alliance:
            alliance = corporation.alliance
        
        if corporation._changed_fields:
            corporation = corporation.save()
        
        return corporation, alliance
    
    def pull_corp(self):
        """Populate corporation details."""
        pass
    
    def pull(self):
        """Pull all details available for this key."""
        
        if self.kind == 'Corporation':
            return self.pull_corp()
        
        try:
            result = api.account.APIKeyInfo(self)  # cached
        except:
            log.exception("Unable to call: APIKeyInfo(%d)", self.key)
            return
        
        if not result.characters.row:
            log.error("No characters returned for key %d?", self.key)
            return
        
        for char in result.characters.row:
            if 'corporationName' not in char:
                log.error("corporationName missing for key %d", self.key)
                continue
            
            self.pull_character(char)
        
        self.modified = datetime.utcnow()
        self.save()
