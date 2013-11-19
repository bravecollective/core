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
    for row in key.rowset.row:
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

import requests

from hashlib import sha256
from datetime import datetime
from xmltodict import parse as parse_xml
from marrow.util.bunch import Bunch
from marrow.templating.serialize.bencode import EnhancedBencode
from mongoengine import Document, IntField, StringField, ListField, DateTimeField, DictField, BooleanField, MapField


class XMLBunch(Bunch):
    def __getattr__(self, name):
        if name not in self:
            if '@' + name not in self:
                self[name]
            
            name = '@' + name
        
        return super(XMLBunch, self).__getattr__(name)



class API(object):
    """A tiny wrapper class to make accessing database-backed API calls more Pythonic."""
    
    def __init__(self, root=None):
        self.root = root
    
    def __getitem__(self, name):
        if self.root:
            return APICall.objects.get(name=self.root + '.' + name)
        
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
                dict(fields=['name', 'mask'], unique=True),
            ]
    )
    
    name = StringField(max_length=200)  # i.e. account.AccountStatus
    kind = StringField(max_length=32, choices=((
            ('m', "Meta"),
            ('c', "Character"),
            ('o', "Corporation")
        )))
    description = StringField()
    mask = IntField()
    group = IntField()
    
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
        uri = self.uri(self.name)
        
        # Define the keyID/vCode API key arguments, if we have credentials.
        if credential:
            payload['keyID'] = credential[0].key
            payload['vCode'] = credential[0].code
        
        # Hash the arguments in a reliable way by converting to text in a way which sorts the keys.
        payload_hash = sha256(EnhancedBencode().encode(payload)).hexdigest()
        
        # Examine the cache.
        cache = CachedAPIValue.objects(
                key = payload.get('keyID', None),
                name = self.name,
                arguments = payload_hash,
                expires__gte = now
            ).first()
        
        if cache:
            return XMLBunch(cache.result)
        
        # Actually perform the query if a cached version could not be found.
        response = requests.post(uri, data=payload or None)
        response.raise_for_status()
        
        # We don't want the initial XML prefix.  We should still check it, though.
        prefix, _, data = response.text.partition('\n')
        
        if prefix.strip() != "<?xml version='1.0' encoding='UTF-8'?>":
            raise Exception("Data returned doesn't seem to be XML!")
        
        data = XMLBunch(parse_xml(data.strip())).eveapi
        result = data.result
        
        if 'rowset' in result and 'row' in result.rowset:
            restruct = XMLBunch()
            
            for rowset in (XMLBunch(i) for i in (result.rowset if isinstance(result.rowset, list) else [result.rowset])):
                restruct[rowset['@name']] = []
                for row in (XMLBunch(i) for i in (rowset.row if isinstance(rowset.row, list) else [rowset.row])):
                    restruct[rowset['@name']].append(row)
            
            result.rowset = restruct
        
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



def populate_calls():
    """Automatically populate the character and corporation APIGroup and APICall instances."""
    
    # from adam.util.api import *
    # a = populate_calls()
    
    type_mapping = dict(Character='c', Corporation='o')
    
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
    
    calls = get_calls()  # Yes, EVE API access is *that* easy.
    #__import__('pudb').set_trace()
    
    # This comprehension is an ugly hack to work around a data format change.
    for row in [i for i in calls.rowset if i['@name'] == 'callGroups'][0]['row']:
        APIGroup(int(row['@groupID']), row['@name'], row['@description']).save()
    
    for row in [i for i in calls.rowset if i['@name'] == 'calls'][0]['row']:
        APICall(
                row['@type'].lower()[:4] + '.' + row['@name'],
                type_mapping[row['@type']],
                row['@description'],
                int(row['@accessMask']),
                int(row['@groupID'])
            ).save()
