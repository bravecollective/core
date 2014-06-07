# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime
from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, EmailField, URLField, DateTimeField, BooleanField, ReferenceField, ListField, IntField

from brave.core.util.signal import update_modified_timestamp
from brave.core.group.acl import ACLRule


log = __import__('logging').getLogger(__name__)

GRANT_WILDCARD = '*'


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
            
    def __repr__(self):
        return "Permission('{0}')".format(self.name)
            
    @staticmethod
    def wildcardPerms(wild):
        """Returns all permissions which wild provides access to. wild should be a string."""
        
        from brave.core.application.model import Application
        
        # If the provided string doesn't contain any wildcards, returnan empty set.
        if GRANT_WILDCARD not in wild:
            return set()
        
        # Mongoengine has no way to find objects based on a regex (as far as I can tell at least...)
        perms = set()
        
        num_wildcards = wild.count(GRANT_WILDCARD)

        # Loops through all of the permissions, then loops through the segments of wild between the periods.
        for perm in Permission.objects():
            # Splits both the wildcard permission provided and the permission being checked.
            wild_segments = wild.split(r'.')
            perm_segments = perm.name.split(r'.')
            
            # Loops through each segment of the wildcard. 'core.example.*.test.*' would have segments of 'core', 
            # 'example', '*', 'test', and '*' in that order.
            for w_seg in wild_segments:
                # We loop through looking for something wrong, if there's nothing wrong then we add it to the set.
                
                # This index is a wildcard, so we skip checks
                if w_seg == GRANT_WILDCARD:
                    continue
                
                # This can occur when the wildcard provided is longer (in terms of segments) than the permission we're
                # checking.
                if wild_segments.index(w_seg) >= len(perm_segments):
                    break
                
                # If this wildcard segment doesn't match the corresponding segment in the permission, this permission
                # doesn't match, and we break to the next permission.
                if not w_seg == perm_segments[wild_segments.index(w_seg)]:
                    break
            else:
                perms.add(perm)        
        
        return perms


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
