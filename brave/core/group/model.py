# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime
from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, EmailField, URLField, DateTimeField, BooleanField, ReferenceField, ListField, IntField

from brave.core.util.signal import update_modified_timestamp
from brave.core.group.acl import ACLRule
from brave.core.permission.model import Permission, WildcardPermission, GRANT_WILDCARD
from brave.core.character.model import EVECharacter


log = __import__('logging').getLogger(__name__)


class GroupCategory(EmbeddedDocument):
    id = StringField(db_field='_id', primary_key=True)
    rank = IntField(db_field='i')
    

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
    join_rules = ListField(EmbeddedDocumentField(ACLRule), db_field='j', default=list)
    request_rules = ListField(EmbeddedDocumentField(ACLRule), db_field='q', default=list)
    
    join_members = ListField(ReferenceField(EVECharacter), db_field='jm', default=list)
    request_members = ListField(ReferenceField(EVECharacter), db_field='rm', default=list)
    requests = ListField(ReferenceField(EVECharacter), db_field='rl', default=list)
    
    creator = ReferenceField('User', db_field='c')
    modified = DateTimeField(db_field='m', default=datetime.utcnow)
    _permissions = ListField(ReferenceField(Permission), db_field='p')
    category = EmbeddedDocumentField(GroupCategory, db_field='ca')
    
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
        
    def add_join_member(self, character):
        """Use this to prevent duplicates in the database"""
        if character in self.join_members:
            return
        
        self.join_members.append(character)
    
    def add_request_member(self, character):
        """Use this to prevent duplicates in the database"""
        if character in self.request_members:
            return
        
        self.request_members.append(character)
        
    def add_request(self, character):
        """Use this to prevent duplicates in the database"""
        if character in self.requests:
            return
            
        self.requests.append(character)

    def __repr__(self):
        return 'Group({0})'.format(self.id).encode('ascii', 'backslashreplace')
    
    def evaluate(self, user, character, rule_set=None):
        if rule_set == "request":
            rules = self.request_rules
        elif rule_set == "join":
            rules = self.join_rules
        else:
            rules = self.rules
        
        for rule in rules:
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
            join_rules=[],
            request_rules=[],
            join_members=[],
            request_members=[],
            requests=[],
        ).save()

        return g
