# encoding: utf-8

"""Caching EVE API access layer.

Yes, it's tied directly to the caching layer.  'Cause why not?

As a few examples:

    # Pull information about a set of credentials.
    key = api.account.APIKeyInfo(credential)
    key.accessMask
    key.type
    key.expires
    
    # Make sure the list of characters is actually a list.  (If there's only one, it might not be.)
    key.rowset.row = key.rowset.row if isinstance(key.rowset.row, list) else [key.rowset.row]
    
    # Once we're sure, list all the characters this key gives access to.
    for row in key.characters:
        row.characterID  # or Name
        row.corporationID  # or Name
    
    # Now that we have a character ID (from the last row up there) we can "Get Info" on them.
    info = api.eve.CharacterInfo(characterID=row.characterID)
    info.race
    info.securityStatus
    
    # If we provide an API key for that character we can get even more information.
    info = api.eve.CharacterInfo(credential, characterID=row.characterID)
    info.accountBalance
    info.lastKnownLocation

"""

from __future__ import print_function

import requests
from web.core import config

from hashlib import sha256
from datetime import datetime
from relaxml import xml
from marrow.util.bunch import Bunch
from marrow.util.convert import boolean, number, array
from marrow.templating.serialize.bencode import EnhancedBencode
from mongoengine import Document, IntField, StringField, ListField, DateTimeField, DictField, BooleanField, MapField, \
    NotUniqueError
from braveapi.client import bunchify as bunchify_lite


log = __import__('logging').getLogger(__name__)


def bunchify(data, name=None):
    if isinstance(data, Bunch):
        return data
    
    if isinstance(data, list):
        if name == 'rowset':  # we unpack these into a dictionary based on name
            return Bunch({i['name']: bunchify(i, 'rowset') for i in data})
        
        return [bunchify(i) for i in data]
    
    if isinstance(data, dict):
        data = data.copy()
        
        if name == 'row' and 'row' in data:
            # Special case of CCP's silly key:value text.
            pass
        
        if name and name in data and not data.get(name, '').strip():
            data.pop(name)
        
        if name == 'rowset' and 'name' in data:
            data.pop('name')
        
        if len(data) == 1 and isinstance(data.values()[0], dict):
            return bunchify(data.values()[0], data.keys()[0])
        
        result = Bunch({
                k: bunchify(
                        [v] if k in ('row', ) and not isinstance(v, list) else v,
                        k
                    ) for k, v in data.iteritems() if k != 'rowset'
            })
        
        if 'rowset' in data:
            rowset = bunchify(data['rowset'] if isinstance(data['rowset'], list) else [data['rowset']], 'rowset')
            result.update(rowset)
        
        if name == 'rowset':  # rowsets always contain rows, even if there are no results
            result.setdefault('row', [])
        
        return result
    
    if isinstance(data, str):
        data = data.decode('utf-8')
    
    if isinstance(data, (str, unicode)):
        try:
            return number(data)
        except ValueError:
            pass
        
        try:
            return boolean(data)
        except ValueError:
            pass
        
        if ',' in data and (name in ('key', 'columns') or ' ' not in data):
            return array(data)
    
    return data


class API(object):
    """A tiny wrapper class to make accessing database-backed API calls more Pythonic."""
    
    def __init__(self, root=None):
        self.root = root
    
    def __getattr__(self, name):
        if self.root:
            try:
                return APICall.objects.get(name=self.root + '.' + name)
            except APICall.DoesNotExist:
                raise AttributeError("api object has no attribute '{0}'".format(self.root + '.' + name))
        
        return self.__class__(name)

api = API()


class APIGroup(Document):
    """Primary classification of API calls."""
    
    meta = dict(
        allow_inheritance = False,
        collection = "APIGroup",
        indexes = [
                dict(fields=['numeric'], unique=True),
            ]
    )
    
    numeric = IntField()
    name = StringField(max_length=200)
    description = StringField(max_length=250)
    
    def __repr__(self):
        return 'APIGroup(%d, "%s")' % (self.numeric, self.name)


class APICall(Document):
    """An EVE API call definition, plus the implementation of actually making these generic calls."""
    
    prefix = "https://api.eveonline.com/"
    suffix = ".xml.aspx"
    
    meta = dict(
        allow_inheritance = False,
        collection = "APICall",
        indexes = [
                dict(fields=['name', '_mask'], unique=True),
            ]
    )
    
    name = StringField(max_length=200)  # i.e. account.AccountStatus
    kind = StringField(max_length=32, choices=((
            ('m', "Meta"),
            ('c', "Character"),
            ('o', "Corporation")
        )))
    description = StringField()
    _mask = IntField(db_field="mask")
    group = IntField()
    # Allow for the name of an APICall to be different from the URI in certain circumstances
    uriname = StringField()
    
    @property
    def mask(self):
        """Returns a Key Mask object instead of just the integer."""
        
        if self.kind == "Meta" or self.kind == "m":
            return EVECharacterKeyMask(self._mask)
        elif self.kind == "Character" or self.kind == "c":
            return EVECharacterKeyMask(self._mask)
        elif self.kind == "Corporation" or self.kind == "o":
            return EVECorporationKeyMask(self._mask)
        else:
            log.info("Incorrect APICall type %s for APICall %s.", self.kind, self.name)
            return None
        
    @mask.setter
    def mask(self, value):
        """Sets the value of the Key Mask"""
        self._mask = value
    
    def __repr__(self):
        return 'APICall(%s, %s)' % (self.name, self.mask or "N/A")
    
    @classmethod
    def uri(cls, call):
        """Formulate a URL for the given call."""
        return cls.prefix + call.replace('.', '/') + cls.suffix
    
    def __call__(self, *credential, **payload):
        """Perform the RPC call while following CCP's caching guidelines."""
        
        if len(credential) > 1:
            raise Exception("The only positional parameter allowed is the credentials object.")
        
        now = datetime.utcnow()
        if not self.uriname:
            uri = self.uri(self.name)
        else:
            uri = self.uri(self.uriname)
        
        # Define the keyID/vCode API key arguments, if we have credentials.
        if credential:
            payload['keyID'] = credential[0].key
            payload['vCode'] = credential[0].code
        
        # Hash the arguments in a reliable way by converting to text in a way which sorts the keys.
        payload_hash = sha256(EnhancedBencode().encode(payload)).hexdigest()
        
        # Examine the cache.
        cv = CachedAPIValue.objects(
                key = payload.get('keyID', None),
                name = self.name,
                arguments = payload_hash,
                expires__gte = now
            ).first()
        
        if cv and cv.current:
            log.info("Returning cached result of %s for key ID %d.", self.name, payload.get('keyID', -1))
            return bunchify_lite(cv.result)
        
        log.info("Making query to %s for key ID %d.", self.name, payload.get('keyID', -1))

        # Provide a User-Agent because CCP asks us to.
        headers = {'User-Agent': 'BRAVE Core Auth; Operated by: {0}'.format(config['core.operator'])}

        # Actually perform the query if a cached version could not be found.
        response = requests.post(uri, data=payload or None, headers=headers)
        response.raise_for_status()
        
        # We don't want the initial XML prefix.  We should still check it, though.
        prefix, _, data = response.text.partition('\n')
        
        if prefix.strip() != "<?xml version='1.0' encoding='UTF-8'?>":
            raise Exception("Data returned doesn't seem to be XML!")
        
        # Encode in UTF-8 to prevent a bug when converting from CML to a dict.
        if isinstance(data, unicode):
            data = data.encode('UTF-8')
        
        data = xml(data)['eveapi']
        result = bunchify(data['result'], 'result')
        data = Bunch(data)
        
        if len(result) == 1:
            result = getattr(result, result.keys()[0])
        
        # Upsert (update if exists, create if it doesn't) the cache value.
        CachedAPIValue.objects(
                key = payload.get('keyID', None),
                name = self.name,
                arguments = payload_hash
            ).update_one(
                upsert = True,
                set__expires = datetime.strptime(data.cachedUntil, "%Y-%m-%d %H:%M:%S"),
                set__result = result
            )
        
        return result


class CachedAPIValue(Document):
    """Data storage for cached API results."""
    
    meta = dict(
            allow_inheritance = False,
            collection = "APICache",
            indexes = [
                    dict(fields=['key', 'name', 'arguments'], unique=True),
                    dict(fields=['expires'], expireAfterSeconds=0)
                ]
        )
    
    key = IntField()
    name = StringField(max_length=200)
    arguments = StringField()  # Stores a hash of the arguments.
    expires = DateTimeField()
    
    result = DictField()
    
    def __repr__(self):
        return "CachedAPIValue(%s, %s)" % (self.name, self.key or "-")
    
    @classmethod
    def current(cls):
        return cls.objects(expires__gte=datetime.utcnow())
    
    @classmethod
    def expired(cls):
        return cls.objects(expires__lt=datetime.utcnow())



def populate_calls(force=False):
    """Automatically populate the character and corporation APIGroup and APICall instances."""
    
    # from adam.util.api import *
    # a = populate_calls()
    
    type_mapping = dict(Character='c', Corporation='o')
    
    if force:
        APICall.drop_collection()
    
    # Just in case we are first bootstrapping the database.
    get_calls, created = APICall.objects.get_or_create(name="api.calllist", defaults=dict(
            name = 'api.calllist',
            kind = 'm',
            description = "Returns the mask and groupings for calls under the new Customizable API Keys authentication method."
        ))
    
    if created:
        # We have more work to do to add the other universal (free-access) API calls.
        
        # Account
        APICall('account.AccountStatus', 'm', "").save()
        APICall('account.APIKeyInfo', 'm', "").save()
        APICall('account.Characters', 'm', "").save()
        
        # EVE Universal
        APICall('eve.AllianceList', 'm', "").save()
        APICall('eve.CertificateTree', 'm', "").save()
        APICall('eve.CharacterID', 'm', "Look up a character's ID based on name.").save()
        APICall('eve.CharacterInfo', 'm', "Get public information about a character").save()
        APICall('eve.CharacterName', 'm', "Look up a character's name based on ID.").save()
        APICall('eve.ConquerableStationList', 'm', "").save()
        APICall('eve.ErrorList', 'm', "").save()
        APICall('eve.FacWarStats', 'm', "").save()
        APICall('eve.FacWarTopStats', 'm', "").save()
        APICall('eve.RefTypes', 'm', "").save()
        APICall('eve.SkillTree', 'm', "").save()
        APICall('eve.TypeName', 'm', "").save()
        
        # EVE Map
        APICall('map.FacWarSystems', 'm', "Returns a list of contestable solarsystems and the NPC faction currently occupying them. It should be noted that this file only returns a non-zero ID if the occupying faction is not the sovereign faction.").save()
        APICall('map.Jumps', 'm', "A list of all systems that have had jumps, presumably in the last hour.").save()
        APICall('map.Kills', 'm', "The number of kills in solarsystems within the last hour.").save()
        APICall('map.Sovereignty', 'm', "Returns a list of solarsystems and what faction or alliance controls them.").save()
        
        # Status
        APICall('server.ServerStatus', 'm', "").save()
    
    result = get_calls()  # Yes, EVE API access is *that* easy.
    
    APIGroup.drop_collection()
    for row in result.callGroups.row:
        APIGroup(row.groupID, row.name, row.description).save()
    
    for row in result.calls.row:
        try:
            if row.type.lower()[:4] == 'char' and row.name == 'CharacterInfo':
                APICall(row.type.lower()[:4] + '.' + row.name + ('Public' if row.accessMask == 8388608 else 'Private'),
                    type_mapping[row.type],
                    row.description,
                    row.accessMask,
                    row.groupID,
                    'eve.CharacterInfo').save()
            else:
                APICall(row.type.lower()[:4] + '.' + row.name,
                    type_mapping[row.type],
                    row.description,
                    row.accessMask,
                    row.groupID).save()
        except NotUniqueError:
            log.info('Call {0} already populated, ignoring'.format(row.name))
            
            
    """Classes for storing, interpreting, and comparing key masks."""
            
class EVEKeyMask:
    """Base class for representing API key masks."""
    
    NULL = 0
    
    def __init__(self, mask):
        self.mask = mask
        
    def __repr__(self):
        return 'EVEKeyMask({0})'.format(self.mask)

    def __nonzero__(self):
        if self.mask:
            return True
        return False
        
    def has_access(self, mask):
        if isinstance(mask, EVEKeyMask):
            mask = mask.mask
        if self.mask & mask == mask:
            return True
            
        return False
        
    def has_multiple_access(self, masks):
        for apiCall in masks:
            if not self.has_access(apiCall):
                return False
        
        return True
        
    def number_of_functions(self):
        """Counts the number of ones in the binary representation of the mask."""
        """This is equivalent to the number of functions that the key provides"""
        """access to as long as the mask is a real mask."""
        return bin(self.mask).count('1')
        
    def functionsAllowed(self):
        """Returns a list with the APICall object of all the functions permitted by this mask."""
        
        funcs = []
        if not self.functions():
            return funcs
            
        for function in self.functions():
            if self.has_access(function.mask.mask):
                funcs.append(function)
        
        return funcs
    
    @staticmethod
    def functions():
        return None
        

class EVECharacterKeyMask(EVEKeyMask):
    """Class for comparing character key masks against the required API calls."""
    
    def __repr__(self):
        return 'EVECharacterKeyMask({0})'.format(self.mask)
        
    @staticmethod
    def functions():
        return APICall.objects(kind='c').order_by('mask')
    
    
class EVECorporationKeyMask(EVEKeyMask):
    """Class for comparing corporation key masks against the required API calls."""
    
    def __repr__(self):
        return 'EVECorporationKeyMask({0})'.format(self.mask)
        
    @staticmethod
    def functions():
        return APICall.objects(kind='o').order_by('mask')
