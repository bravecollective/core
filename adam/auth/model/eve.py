# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime

from mongoengine import Document, StringField, DateTimeField, BooleanField, ReferenceField, IntField

from adam.auth.model.signals import update_modified_timestamp, trigger_api_validation


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
    verified = BooleanField(db_field='v', default=False)
    expires = DateTimeField(db_field='e')
    owner = ReferenceField('User', db_field='o', reverse_delete_rule='CASCADE')
    
    modified = DateTimeField(db_field='m', default=datetime.utcnow)


@update_modified_timestamp.signal
class EVEEntity(Document):
    meta = dict(
            allow_inheritance = True,
        )
    
    identifier = IntField(db_field='i', unique=True)
    name = StringField(db_field='n')
    
    modified = DateTimeField(db_field='m', default=datetime.utcnow)


class EVEAlliance(EVEEntity):
    pass


class EVECorporation(EVEEntity):
    alliance = ReferenceField(EVEAlliance)


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
