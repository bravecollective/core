# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime
from mongoengine import Document, StringField, DateTimeField, ReferenceField, IntField, BooleanField
from brave.core.util.signal import update_modified_timestamp
from brave.core.key.model import EVECredential


log = __import__('logging').getLogger(__name__)


@update_modified_timestamp.signal
class EVEEntity(Document):
    meta = dict(
            allow_inheritance = True,
            indexes = [
                    'identifier'
                ],
        )
    
    identifier = IntField(db_field='i', unique=True)
    name = StringField(db_field='n')
    
    modified = DateTimeField(db_field='m', default=datetime.utcnow)
    
    def __repr__(self):
        return '{0}({1}, {2}, "{3}")'.format(self.__class__.__name__, self.id, self.identifier, self.name)
    
    def __unicode__(self):
        return self.name


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
    
    alliance = ReferenceField(EVEAlliance)
    corporation = ReferenceField(EVECorporation)
    
    owner = ReferenceField('User', db_field='o', reverse_delete_rule='NULLIFY')
    credential = ReferenceField(EVECredential, db_field='r', reverse_delete_rule='NULLIFY')
    default = BooleanField(db_field='d')
