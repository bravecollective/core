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
    _mask = IntField(db_field='a', default=0)
    verified = BooleanField(db_field='v', default=False)
    expires = DateTimeField(db_field='e')
    owner = ReferenceField('User', db_field='o', reverse_delete_rule='CASCADE')
    
    modified = DateTimeField(db_field='m', default=datetime.utcnow)
    
    def __repr__(self):
        return 'EVECredential({0}, {1}, {2}, {3!r})'.format(self.id, self.kind, self._mask, self.owner)
    
    @property
    def characters(self):
        from brave.core.character.model import EVECharacter
        return EVECharacter.objects(credentials=self)
        
    @property
    def mask(self):
        """Returns a Key Mask object instead of just the integer."""
        if self.kind == "Account":
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
        except NotUniqueError:
            char = EVECharacter.objects(identifier=info.characterID)[0]
        
        if self.mask.has_access(EVECharacterKeyMask.CHARACTER_SHEET):
            info = api.char.CharacterSheet(self, characterID=info.characterID)
        elif self.mask.has_access(EVECharacterKeyMask.CHARACTER_INFO_PUBLIC):
            info = api.eve.CharacterInfo(self, characterID=info.characterID)

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
        self.verified = self._mask != 0
        
        if not result.characters.row:
            log.error("No characters returned for key %d?", self.key)
            return self
        
        for char in result.characters.row:
            if 'corporationName' not in char:
                log.error("corporationName missing for key %d", self.key)
                continue
            
            self.pull_character(char)
        
        self.modified = datetime.utcnow()
        self.save()
        return self

class EVEKeyMask:
    """Base class for representing API key masks."""
    
    NULL = 0
    
    def __init__(self, mask):
        self.mask = mask
        
    def __repr__(self):
        return 'EVEKeyMask({0})'.format(self.mask)
        
    def has_access(self, mask):
        if self.mask & mask:
            return True
            
        return False
        
    def has_multiple_access(self, masks):
        for apiCall in masks:
            if not self.mask & apiCall:
                return False
        
        return True
        
    def number_of_functions(self):
        """Counts the number of ones in the binary representation of the mask."""
        """This is equivalent to the number of functions that the key provides"""
        """access to as long as the mask is a real mask."""
        return bin(self._mask).count('1')

class EVECharacterKeyMask(EVEKeyMask):
    """Class for comparing character key masks against the required API calls."""
    
    ACCOUNT_BALANCE = 1
    ASSET_LIST = 2
    CALENDAR_EVENT_ATTENDEES = 4
    CHARACTER_SHEET = 8
    CONTACT_LIST = 16
    CONTACT_NOTIFICATIONS = 32
    FAC_WAR_STATS = 64
    INDUSTRY_JOBS = 128
    KILL_LOG = 256
    MAIL_BODIES = 512
    MAILING_LISTS = 1024
    MAIL_MESSAGES = 2048
    MARKET_ORDERS = 4096
    MEDALS = 8192
    NOTIFICATIONS = 16384
    NOTIFICATION_TEXTS = 32768
    RESEARCH = 65536
    SKILL_IN_TRAINING = 131072
    SKILL_QUEUE = 262144
    STANDINGS = 524288
    UPCOMING_CALENDAR_EVENTS = 1048576
    WALLET_JOURNAL = 2097152
    WALLET_TRANSACTIONS = 4194304
    CHARACTER_INFO_PUBLIC = 8388608
    CHARACTER_INFO_PRIVATE = 16777216
    ACCOUNT_STATUS = 33554432
    CONTRACTS = 67108864
    LOCATIONS = 134217728
    
    def __repr__(self):
        return 'EVECharacterKeyMask({0})'.format(self.mask)
    
class EVECorporationKeyMask(EVEKeyMask):
    """Class for comparing corporation key masks against the required API calls."""
    
    ACCOUNT_BALANCE = 1
    ASSET_LIST = 2
    MEMBER_MEDALS = 4
    CORPORATION_SHEET = 8
    CONTACT_LIST = 16
    CONTAINER_LOG = 32
    FAC_WAR_STATS = 64
    INDUSTRY_JOBS = 128
    KILL_LOG = 256
    MEMBER_SECURITY = 512
    MEMBER_SECURITY_LOG = 1024
    MEMBER_TRACKING_LIMITED = 2048
    MARKET_ORDERS = 4096
    MEDALS = 8192
    OUTPOST_LIST = 16384
    OUTPOST_SERVICE_DETAIL = 32768
    SHAREHOLDERS = 65536
    STARBASE_DETAIL = 131072
    STANDINGS = 262144
    STARBASE_LIST = 524288
    WALLET_JOURNAL = 1048576
    WALLET_TRANSACTIONS = 2097152
    TITLES = 4194304
    CONTRACTS = 8388608
    LOCATIONS = 16777216
    MEMBER_TRACKING_EXTENDED = 33554432
    
    def __repr__(self):
        return 'EVECorporationKeyMask({0})'.format(self.mask)
