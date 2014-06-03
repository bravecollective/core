# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime
from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, EmailField, URLField, DateTimeField, BooleanField, ReferenceField, ListField, IntField

from brave.core.util.signal import update_modified_timestamp
from brave.core.group.acl import ACLRule


log = __import__('logging').getLogger(__name__)


class Permission(Document):
    meta = dict(
        collection='Permissions',
        allow_inheritance = False,
        indexes = [
            dict(fields=['name'], unique=True, required=True)
        ],
    )
    
    name = StringField(db_field='n')
    description = StringField(db_field='d')
    
    @property
    def application(self):
        from brave.core.application.model import Application
        
        app_short = name[:(name.index('.')-1)]
        
        app = Application.objects(short=app_short)
        
        if not len(app):
            return None
        else:
            return app.first()


@update_modified_timestamp.signal
class Group(Document):
    meta = dict(
            collection = 'Groups',
            allow_inheritance = False,
            indexes = [],
        )
    
    id = StringField(db_field='_id', primary_key=True)
    title = StringField(db_field='t')
    rules = ListField(EmbeddedDocumentField(ACLRule), db_field='r')
    
    creator = ReferenceField('User', db_field='c')
    modified = DateTimeField(db_field='m', default=datetime.utcnow)
    permissions = ListField(ReferenceField(Permission), db_field='p')

    def __repr__(self):
        return 'Group({0})'.format(self.id).encode('ascii', 'backslashreplace')
    
    def evaluate(self, user, character):
        for rule in self.rules:
            result = rule.evaluate(user, character)
            if result is not None:
                return result
        
        return False  # deny by default

    @staticmethod
    def create(id, title, user, rules=[]):
        # This is unavoidably racy.
        g = Group.objects(id=id)
        if g:
            return None
        g = Group(id=id,
            title=title,
            rules=[],
            creator=user._current_obj(),
            modified=datetime.utcnow(),
        ).save()

        return g
