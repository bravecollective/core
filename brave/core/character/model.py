# encoding: utf-8

from __future__ import unicode_literals

from collections import OrderedDict
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
    
    @property
    def tags(self):
        from brave.core.group.model import Group
        mapping = dict()
        
        for group in Group.objects:
            if group.evaluate(self.owner, self):
                mapping[group.id] = group
        
        def titlesort(i):
            return mapping[i].title
        
        return OrderedDict((i, mapping[i]) for i in sorted(mapping.keys(), key=titlesort))
