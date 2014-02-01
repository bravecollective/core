# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime
from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, EmailField, URLField, DateTimeField, BooleanField, ReferenceField, ListField, IntField

from brave.core.util.signal import update_modified_timestamp


log = __import__('logging').getLogger(__name__)


@update_modified_timestamp.signal
class Group(Document):
    meta = dict(
            collection = 'Groups',
            allow_inheritance = False,
            indexes = [],
        )
    
    id = StringField(db_field='_id', primary_key=True)
    title = StringField(db_field='t')
    rules = LsitField(EmbeddedDocumentField(ACLRule), db_field='r')
    
    creator = ReferenceField('User', db_field='c')
    modified = DateTimeField(db_field='m', default=datetime.utcnow)
    
    def evaluate(self, user, character):
        for rule in self.rules:
            result = rule.evaluate(user, character)
            if result is not None:
                return result
        
        return False  # deny by default
