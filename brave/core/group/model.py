# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime
from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, EmailField, URLField, DateTimeField, BooleanField, ReferenceField, ListField, IntField

from brave.core.util.signal import update_modified_timestamp
from brave.core.group.acl import ACLRule
from brave.core.permission.model import Permission, WildcardPermission
from brave.core.character.model import EVECharacter


log = __import__('logging').getLogger(__name__)


class GroupCategory(Document):
    meta = dict(
            collection = 'GroupCategories',
            allow_inheritance = False,
            indexes = [],
        )
    
    name = StringField(db_field='name')
    rank = IntField(db_field='i')
    members = ListField(ReferenceField('Group'), db_field='m', default=list)
    

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
    
    # Permissions
    VIEW_PERM = 'core.group.view.{group_id}'
    EDIT_ACL_PERM = 'core.group.edit.acl.{group_id}'
    EDIT_PERMS_PERM = 'core.group.edit.perms.{group_id}'
    EDIT_MEMBERS_PERM = 'core.group.edit.members.{group_id}'
    EDIT_REQUESTS_PERM = 'core.group.edit.requests.{group_id}'
    EDIT_TITLE_PERM = 'core.group.edit.title.{group_id}'
    EDIT_ID_PERM = 'core.group.edit.id.{group_id}'
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
        
    def add_join_member(self, character):
        """Use this to prevent duplicates in the database when not checking if a user is already in the list, does not
            prevent duplicates due to concurrent modification."""
        if character in self.join_members:
            return
        
        self.join_members.append(character)
    
    def add_request_member(self, character):
        """Use this to prevent duplicates in the database when not checking if a user is already in the list, does not
            prevent duplicates due to concurrent modification."""
        if character in self.request_members:
            return
        
        self.request_members.append(character)
        
    def add_request(self, character):
        """Use this to prevent duplicates in the database when not checking if a user is already in the list, does not
            prevent duplicates due to concurrent modification."""
        if character in self.requests:
            return
            
        self.requests.append(character)

    def __repr__(self):
        return 'Group({0})'.format(self.id).encode('ascii', 'backslashreplace')
    
    def evaluate(self, user, character, rule_set=None):
        # If the character has no owner (and therefore no API key), deny them access to every group.
        if not character.owner:
            return False

        if rule_set == "request":
            rules = self.request_rules
        elif rule_set == "join":
            rules = self.join_rules
        elif rule_set == "main":
            # Allow evaluating the main group of rules without considering people who joined a group.
            rules = self.rules
        else:
            # Checking if a user is a member of this group... so we need to see if they've joined/been accepted
            # Cascade down to further checks in case they joined or applied to join, then lost the ability to do so
            # but is now automatically granted access to the group.
            # TODO: Perhaps automatically clean up the join lists when a character no longer applies?
            if character in self.join_members:
                if self.evaluate(user, character, rule_set='join'):
                    return True
            if character in self.request_members:
                if self.evaluate(user, character, rule_set='request'):
                    return True
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

    def rename(self, new_name):
        """Can't modify the primary key in Mongoengine, so we have to recreate a new group then delete this one."""
        g = Group(id=new_name, title=self.title, rules=self.rules, join_rules=self.join_rules, request_rules=self.request_rules,
                        join_members=self.join_members, request_members=self.request_members, requests=self.requests,
                        creator=self.creator, modified=datetime.utcnow, _permissions=self._permissions)

        g = g.save()

        for gc in GroupCategory.objects(members=self):
            gc.members.remove(self)
            gc.members.append(g)
            gc.save()

        self.delete()
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
    def edit_members_perm(self):
        return self.get_perm('EDIT_MEMBERS')
        
    @property
    def edit_requests_perm(self):
        return self.get_perm('EDIT_REQUESTS')
        
    @property
    def delete_perm(self):
        return self.get_perm('DELETE')
