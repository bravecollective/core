# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime
from mongoengine import Document, StringField, DateTimeField, BooleanField, ReferenceField, IntField
from marrow.util.bunch import Bunch

from brave.core.util import strip_tags
from brave.core.util.signal import update_modified_timestamp, trigger_api_validation


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
            ) if 'allianceID' in info else (None, False)
        
        if alliance and not created and alliance.name != allianceName:
            alliance.name = allianceName
            alliance = alliance.save()
            
        corporation, created = EVECorporation.objects.get_or_create(
                identifier = info.corporationID,
                defaults = dict(name=info.corporationName, alliance=alliance)
            )
        
        if corporation.name != info.corporationName:
            corporation.name = info.corporationName
        
        if alliance and corporation.alliance != alliance:
            corporation.alliance = alliance
        
        if corporation._changed_fields:
            corporation = corporation.save()
        
        return corporation, alliance
    
    def pull_minimal(self, info):
        """Populate character details given nothing but a validated API key."""
        from brave.core.character.model import EVECharacter
        
        corporation, alliance = self.get_membership(info)
        
        char, created = EVECharacter.objects.get_or_create(
                owner = self.owner,
                identifier = info.characterID
            )
        
        if self not in char.credentials:
            char.credentials.append(self)
        
        char.name = info.characterName if 'characterName' in info else info.name
        char.corporation = corporation
        
        if alliance: char.alliance = alliance
        
        return char.save(), corporation, alliance
    
    def pull_basic(self, info):
        """Populate character details using an authenticated eve.CharacterInfo call."""
        from brave.core.util.eve import APICall
        
        log.info('pull_basic')
        
        try:
            results = APICall.objects.get(name='eve.CharacterInfo')(self, characterID=info.characterID)
        except:
            log.exception("Unable to retrieve character information for: %d", info.characterID)
            return None, None, None
        
        results = Bunch({k.replace('@', ''): int(v) if isinstance(v, (unicode, str)) and v.isdigit() else v for k, v in results.iteritems()})
        
        char, corporation, alliance = self.pull_minimal(results)
        
        char.race = results.race
        char.bloodline = results.bloodLine if 'bloodLine' in info else results.bloodline
        char.security = float(results.securityStatus)
        char.save()
        
        return char, corporation, alliance
    
    def pull_full(self, info):
        """Populate character details using a character.CharacterSheet call."""
        from brave.core.util.eve import APICall
        
        log.info('pull_full')
        
        try:
            results = APICall.objects.get(name='char.CharacterSheet')(self, characterID=info.characterID)
        except:
            log.exception("Unable to retrieve character sheet for: %d", info.characterID)
            return None, None, None
        
        results = Bunch({k.replace('@', ''): int(v) if isinstance(v, (unicode, str)) and v.isdigit() else v for k, v in results.iteritems()})
    
        char, corporation, alliance = self.pull_minimal(results)
        if not char: return None, None, None
        
        # Pivot the returned rowsets.
        data = Bunch()
        for row in results.rowset:
            if 'row' not in row: continue
            data[row['@name']] = row['row'] if isinstance(row['row'], list) else [row['row']]
        
        char.titles = [strip_tags(i['@titleName']) for i in data.corporationTitles] if 'corporationTitles' in data else []
        char.roles = [i['@roleName'] for i in data.corporationRoles] if 'corporationRoles' in data else []
        
        char.save()
        
        return char, corporation, alliance
    
    def pull_corp(self):
        """Populate corporation details."""
        pass
    
    def pull(self):
        """Pull all details available for this key."""
        
        from brave.core.util.eve import APICall
        
        if self.kind == 'Corporation':
            return self.pull_corp()
        
        try:
            result = APICall.objects.get(name='account.APIKeyInfo')(self)  # cached
        except:
            log.exception("Unable to call: account.APIKeyInfo(%d)", self.key)
            return
        
        if self.mask & 8:  # character.CharacterSheet
            implementation = self.pull_full
        elif self.mask & 8388608:  # eve.CharacterInfo
            implementation = self.pull_basic
        else:
            implementation = self.pull_minimal
        
        if 'row' not in result.key.rowset:
            log.error("No characters returned for key %d?", self.key)
            return
        
        for char in result.key.rowset.row if isinstance(result.key.rowset.row, list) else [result.key.rowset.row]:
            if 'corporationName' not in char: continue
            char = Bunch({k.replace('@', ''): int(v) if v.isdigit() else v for k, v in char.iteritems()})
            implementation(char)
        
        self.modified = datetime.utcnow()
        self.save()
