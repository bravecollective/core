# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime
from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, EmailField, URLField, DateTimeField, BooleanField, ReferenceField, ListField, IntField

from brave.core.util.signal import update_modified_timestamp
from brave.core.group.acl import ACLRule
from brave.core.permission.model import Permission, WildcardPermission


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
    rules = ListField(EmbeddedDocumentField(ACLRule), db_field='r')
    
    creator = ReferenceField('User', db_field='c')
    modified = DateTimeField(db_field='m', default=datetime.utcnow)
    _permissions = ListField(ReferenceField(Permission), db_field='p')
    
    # Permissions
    VIEW_PERM = 'core.group.view.{group_id}'
    EDIT_ACL_PERM = 'core.group.edit.acl.{group_id}'
    EDIT_PERMS_PERM = 'core.group.edit.perms.{group_id}'
    DELETE_PERM = 'core.group.delete.{group_id}'
    CREATE_PERM = 'core.group.create'
    
    @property
    def permissions(self):
        """Returns the permissions that this group grants as Permission objects. Evaluates the wildcard permissions
            as well."""
        
        perms = set()
        
        for perm in self._permissions:
            # if perm is not a wildcard permission, add it to the set.
            if not isinstance(perm, WildcardPermission):
                perms.add(perm)
                continue
                
            for p in perm.get_permissions():
                perms.add(p)
                
        return perms

    def __repr__(self):
        return 'Group({0})'.format(self.id).encode('ascii', 'backslashreplace')
    
    def evaluate(self, user, character):
        
        # If the character has no owner (and therefore no API key), deny them access to every group.
        if not character.owner:
            return False
        
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
        
    def get_perm(self, perm_type):
        return getattr(self, perm_type+"_PERM").format(group_id=self.id)
        
    @property
    def view_perm(self):
        return self.get_perm('VIEW')
        
    @property
    def edit_acl_perm(self):
        return self.get_perm('EDIT_ACL')
        
    @property
    def edit_perms_perm(self):
        return self.get_perm('EDIT_PERMS')
        
    @property
    def delete_perm(self):
        return self.get_perm('DELETE')
