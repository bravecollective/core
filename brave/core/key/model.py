# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime
from mongoengine import Document, StringField, DateTimeField, BooleanField, ReferenceField, IntField
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
    
    def pull_minimal(self, info):
        """Populate character details given nothing but a validated API key."""
        from brave.core.character.model import EVECharacter
        
        corporation, alliance = self.get_membership(info)
        
        try:
            char, created = EVECharacter.objects.get_or_create(
                    owner = self.owner,
                    identifier = info.characterID
                )
        except:
            log.exception("failed to get/create character for key %d", self.key)
            return None, None, None
        
        if self not in char.credentials:
            char.credentials.append(self)
        
        char.name = info.characterName if 'characterName' in info else info.name
        char.corporation = corporation
        
        if alliance: char.alliance = alliance
        
        return char.save(), corporation, alliance
    
    def pull_basic(self, info):
        """Populate character details using an authenticated eve.CharacterInfo call."""
        
        log.info('pull_basic')
        
        try:
            results = api.eve.CharacterInfo(self, characterID=info.characterID)
        except:
            log.exception("Unable to retrieve character information for: %d", info.characterID)
            return None, None, None
        
        info = Bunch({k.replace('@', ''): int(v) if isinstance(v, (unicode, str)) and v.isdigit() else v for k, v in results.iteritems()})
        
        char, corporation, alliance = self.pull_minimal(info)
        
        char.race = info.race
        char.bloodline = info.bloodLine if 'bloodLine' in info else info.bloodline
        char.security = info.securityStatus
        char.save()
        
        return char, corporation, alliance
    
    def pull_full(self, info):
        """Populate character details using a character.CharacterSheet call."""
        
        log.info('pull_full')
        
        try:
            info = api.char.CharacterSheet(self, characterID=info.characterID)
        except:
            log.exception("Unable to retrieve character sheet for: %d", info.characterID)
            return None, None, None
        
        char, corporation, alliance = self.pull_minimal(info)
        if not char: return None, None, None
        
        char.titles = [strip_tags(i.titleName) for i in info.corporationTitles.row] if 'corporationTitles' in info else []
        char.roles = [i.roleName for i in info.corporationRoles.row] if 'corporationRoles' in info else []
        
        char.save()
        
        return char, corporation, alliance
    
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
        
        if self.mask & 8 == 8:  # character.CharacterSheet
            implementation = self.pull_full
        elif self.mask & 8388608 == 8388608:  # eve.CharacterInfo
            implementation = self.pull_basic
        else:
            implementation = self.pull_minimal
        
        if not result.characters.row:
            log.error("No characters returned for key %d?", self.key)
            return
        
        for char in result.characters.row:
            if 'corporationName' not in char:
                log.error("corporationName missing for key %d", self.key)
                continue
            
            implementation(char)
        
        self.modified = datetime.utcnow()
        self.save()
