# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime

from mongoengine import Document, StringField, DateTimeField, BooleanField, ReferenceField, IntField

from adam.auth.model.signals import update_modified_timestamp, trigger_api_validation
from adam.api import APICall


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

    def importChars(self):
        result = APICall.objects.get(name='account.APIKeyInfo')(self)
        key = result.key
        if isinstance(key.rowset.row, list):
            rows = key.rowset.row
        else:
            rows = [key.rowset.row]

        for row in rows:
            charID = row['@characterID']
            info = APICall.objects.get(name='eve.CharacterInfo')(self, characterID=charID)
            print info
            alliance = EVEAlliance.get_or_create(info.alliance, info.allianceID)
            corporation = EVECorporation.get_or_create(info.corporation,
                    info.corporationID, alliance)
            character = EVECharacter(owner=self.owner, credential=self,
                    name=info.characterName, corporation=corporation,
                    alliance=alliance, identifier=charID)
            character.save()



@update_modified_timestamp.signal
class EVEEntity(Document):
    meta = dict(
            allow_inheritance = True,
        )
    
    identifier = IntField(db_field='i', unique=True)
    name = StringField(db_field='n')
    
    modified = DateTimeField(db_field='m', default=datetime.utcnow)


class EVEAlliance(EVEEntity):
    @staticmethod
    def get_or_create(name, identifier):
        alliance, created = EVEAlliance.objects.get_or_create(name=name,
                identifier=identifier)
        return alliance
    pass


class EVECorporation(EVEEntity):
    alliance = ReferenceField(EVEAlliance)

    @staticmethod
    def get_or_create(name, identifier, alliance):
        corp, created = EVECorporation.objects.get_or_create(name=name,
                identifier=identifier, alliance=alliance)


class EVECharacter(EVEEntity):
    meta = dict(
        indexes = [
                'owner',
            ],
    )
    
    owner = ReferenceField('User', db_field='o', reverse_delete_rule='NULLIFY')
    credential = ReferenceField(EVECredential, db_field='r', reverse_delete_rule='NULLIFY')

    corporation = ReferenceField(EVEEntity, db_field='c')
    alliance = ReferenceField(EVEEntity, db_field='a')
    
    modified = DateTimeField(db_field='m', default=datetime.utcnow)
