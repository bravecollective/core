# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime
from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, EmailField, URLField, DateTimeField, BooleanField, ReferenceField, ListField, IntField

from brave.core.util.signal import update_modified_timestamp


log = __import__('logging').getLogger(__name__)

GRANT_WILDCARD = '*'


class Permission(Document):
    meta = dict(
        collection='Permissions',
        allow_inheritance = True,
        indexes = [
            dict(fields=['name'], unique=True, required=True)
        ],
    )
    
    name = StringField(db_field='n')
    description = StringField(db_field='d')
    
    @property
    def application(self):
        """Returns the application that this permission is for."""
        
        from brave.core.application.model import Application
        
        # Handle '*' properly
        if self.name.find('.') == -1:
            return None
        
        app_short = self.name.split('.')[0]
        
        app = Application.objects(short=app_short)
        
        if not len(app):
            return None
        else:
            return app.first()
            
    def __repr__(self):
        return "Permission('{0}')".format(self.name)
            
    def getPermissions(self):
        """Returns all permissions granted by this Permission."""
        
        return set({self})
        
class WildcardPermission(Permission):
    
    def __repr__(self):
        return "WildcardPermission('{0}')".format(self.name)
            
    def getPermissions(self):
        """Returns all Permissions granted by this Permission"""
        
        from brave.core.application.model import Application
        
        # Mongoengine has no way to find objects based on a regex (as far as I can tell at least...)
        perms = set()

        # Loops through all of the permissions, then loops through the segments of this wildcardPerm between the periods.
        for perm in Permission.objects():
            # Splits both this permission's name and the permission being checked.
            self_segments = self.name.split('.')
            perm_segments = perm.name.split('.')
            
            # If this permission has more segments than the permission we're matching against, it can't provide access
            # to that permission, so we skip it.
            if len(self_segments) > len(perm_segments):
                continue
            
            # Loops through each segment of the wildcardPerm and permission name. 'core.example.*.test.*' would have 
            # segments of 'core', 'example', '*', 'test', and '*' in that order.
            for (s_seg, perm_seg) in zip(self_segments, perm_segments):
                # We loop through looking for something wrong, if there's nothing wrong then we add it to the set.
                
                # This index is a wildcard, so we skip checks
                if s_seg == GRANT_WILDCARD:
                    continue
                
                # If this self segment doesn't match the corresponding segment in the permission, this permission
                # doesn't match, and we break to the next permission.
                if s_seg != perm_seg:
                    break
                
            else:
                perms.add(perm)        
        
        return perms
