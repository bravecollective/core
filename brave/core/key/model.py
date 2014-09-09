# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime
from mongoengine import Document, StringField, DateTimeField, BooleanField, ReferenceField, IntField
from mongoengine.errors import NotUniqueError
from requests.exceptions import HTTPError

from brave.core.account.model import User
from brave.core.util import strip_tags
from brave.core.util.signal import update_modified_timestamp, trigger_api_validation
from brave.core.util.eve import api, EVECharacterKeyMask, EVECorporationKeyMask

from web.core import config

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
                    dict(fields=['expires'], expireAfterSeconds=0),
                    dict(fields=['key'], unique=True)
                ],
        )
    
    key = IntField(db_field='k', unique=True)
    code = StringField(db_field='c')
    kind = StringField(db_field='t')
    _mask = IntField(db_field='a', default=0)
    verified = BooleanField(db_field='v', default=False)
    expires = DateTimeField(db_field='e')
    owner = ReferenceField('User', db_field='o', reverse_delete_rule='CASCADE')
    # the violation field is used to indicate some sort of conflict for a key. 
    # A value of 'Character' means that a key gives access to a character which 
    # is already attached to a different account than the owner of the key.
    # A value of 'Kind' means the key does not meet the recommended key type
    # A value of 'Mask' means the key does not meet the recommended key mask
    # A value of None is used to indicate no problem
    violation = StringField(db_field='s')
    
    modified = DateTimeField(db_field='m', default=datetime.utcnow)
    
    # Permissions
    VIEW_PERM = 'core.key.view.{credential_key}'
    LIST_PERM = 'core.key.list.all'
    
    def __repr__(self):
        return 'EVECredential({0}, {1}, {2}, {3!r})'.format(self.id, self.kind, self._mask, self.owner)
    
    def delete(self):
        # Detach any character that this key provides access to, but that the owner no longer has a key for.
        for char in self.characters:
            # Make sure not to include this key when checking if there are still keys for the character
            if len([c for c in char.credentials if c.id != self.id]) == 0:
                char.detach()
                
        super(EVECredential, self).delete()
    
    @property
    def characters(self):
        from brave.core.character.model import EVECharacter
        return EVECharacter.objects(credentials=self)
        
    @property
    def mask(self):
        """Returns a Key Mask object instead of just the integer."""
        
        if self.kind == "Account":
            return EVECharacterKeyMask(self._mask)
        elif self.kind == "Character":
            return EVECharacterKeyMask(self._mask)
        elif self.kind == "Corporation":
            return EVECorporationKeyMask(self._mask)
        else:
            log.info("Incorrect key type %s for key %s.", self.kind, self.key)
            return None
        
    @mask.setter
    def mask(self, value):
        """Sets the value of the Key Mask"""
        self._mask = value
    
    # EVE API Integration

    def pull_character(self, info):
        """This always updates all information on the character, so that we do not end up with
        inconsistencies. There is some weirdness that, if a user already has a key with full
        permissions, and adds a limited one, we'll erase information on that character. We should
        probably check for and refresh info from the most-permissioned key instead of this."""
        from brave.core.character.model import EVEAlliance, EVECorporation, EVECharacter
        try:
            char = EVECharacter(identifier=info.characterID).save()
            new = True
        except NotUniqueError:
            char = EVECharacter.objects(identifier=info.characterID)[0]
            new = False
            
            if char.owner and self.owner != char.owner:
                log.warning("Security violation detected. Multiple accounts trying to register character %s, ID %d. "
                            "Actual owner is %s. User adding this character is %s.",
                            char.name, info.characterID,
                            EVECharacter.objects(identifier=info.characterID).first().owner, self.owner)
                self.violation = "Character"
                
                # Mark both accounts as duplicates of each other.
                User.add_duplicate(self.owner, char.owner)
        
                return

        try:
            if self.mask.has_access(api.char.CharacterSheet.mask):
                info = api.char.CharacterSheet(self, characterID=info.characterID)
            elif self.mask.has_access(api.char.CharacterInfoPublic.mask):
                info = api.char.CharacterInfoPublic(self, characterID=info.characterID)
        except Exception:
            log.warning("An error occured while querying data for key %s.", self.key)
            if new:
                char.delete()
            
            raise

        char.corporation, char.alliance = self.get_membership(info)

        char.name = info.name if 'name' in info else info.characterName
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
        return char
    
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
        return self
    
    def eval_violation(self):
        """Sets the value of the field 'violation'. NOTE: Does not handle violations of type 'Character'"""
        try:
            rec_mask = int(config['core.recommended_key_mask'])
            kind_acceptable = self.kind == config['core.recommended_key_kind']
            # Account keys are acceptable in place of Character keys
            if not kind_acceptable and config['core.recommended_key_kind'] == 'Character' and self.kind == 'Account':
                kind_acceptable = True
            
            if self.violation == 'Character':
                return
            
            if not kind_acceptable:
                self.violation = 'Kind'
                return self.save()
            
            if not self.mask.has_access(rec_mask):
                self.violation = 'Mask'
                return self.save()
                
            self.violation = None
            return self.save()
            
        except ValueError:
            log.warn("core.recommended_key_mask MUST be an integer.")
    
    def pull(self):
        """Pull all details available for this key.
        
        If this key isn't valid (can't call APIKeyInfo on it), then this object will delete itself
        and return None. Probably call this like "cred = cred.pull()"."""
        
        if self.kind == 'Corporation':
            return self.pull_corp()
        
        try:
            result = api.account.APIKeyInfo(self)  # cached
        except HTTPError as e:
            if e.response.status_code == 403:
                log.debug("key disabled; deleting %d" % self.key)
                self.delete()
                return None
            log.exception("Unable to call: APIKeyInfo(%d)", self.key)
            return
        
        self.mask = int(result['accessMask'])
        self.kind = result['type']
        self.expires = datetime.strptime(result['expires'], '%Y-%m-%d %H:%M:%S') if result.get('expires', None) else None
        
        try:
            rec_mask = int(config['core.recommended_key_mask'])
            kind_acceptable = self.kind == config['core.recommended_key_kind']
            # Account keys are acceptable in place of Character keys
            if not kind_acceptable and config['core.recommended_key_kind'] == 'Character' and self.kind == 'Account':
                kind_acceptable = True
            
            self.verified = self.mask.has_access(rec_mask) and kind_acceptable
        except ValueError:
            log.warn("core.recommended_key_mask MUST be an integer.")
            self.verified = False
        
        if not result.characters.row:
            log.error("No characters returned for key %d?", self.key)
            return self
        
        allCharsOK = True

        for char in result.characters.row:
            if 'corporationName' not in char:
                log.error("corporationName missing for key %d", self.key)
                continue
            
            if not self.pull_character(char):
                allCharsOK = False
        
        if allCharsOK and self.violation == "Character":
            self.violation = None
        
        self.eval_violation()
        
        self.modified = datetime.utcnow()
        self.save()
        return self
    
    @property
    def view_perm(self):
        return self.VIEW_PERM.format(credential_key=str(self.key))
