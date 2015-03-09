# encoding: utf-8

from __future__ import unicode_literals

import itertools

from datetime import datetime
from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, EmailField, URLField, DateTimeField, BooleanField, ReferenceField, ListField, IntField, Q, signals

from brave.core.util.signal import update_modified_timestamp
from brave.core.group.acl import ACLRule, ACLGroupMembership, CyclicGroupReference
from brave.core.permission.model import Permission, WildcardPermission
from brave.core.character.model import EVECharacter


log = __import__('logging').getLogger(__name__)


class GroupReferenceException(Exception):
    def __init__(self, referencers):
        self.referencers = referencers
    def __unicode__(self):
        return "Referenced by existing groups: {}".format(self.referencers)


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


    @classmethod
    def pre_save(cls, sender, document, **kwargs):
        document.cycle_check()

    @classmethod
    def pre_delete(cls, sender, document, **kwargs):
        references = document.get_references()
        if len(references):
            raise GroupReferenceException(references)

    def get_references(self):
        # mongo is stupid and/or I am stupid, so I cannot figure out how to do
        # this in the db.
        ids = [g.id for g in Group.objects().only('rules', 'join_rules', 'request_rules')
               if any(isinstance(r, ACLGroupMembership) and r.group.id == self.id
                      for r in itertools.chain(g.rules, g.join_rules, g.request_rules))]
        groups = Group.objects(**{'id__in': ids})
        assert len(ids) == len(groups)
        return groups
    
    @property
    def permissions(self):
        """Returns the permissions that this group grants as Permission objects. Note, this is mostly here for backwards
        compatibility from when we evaluated Wildcard permissions out into all known Permissions (which we stopped doing
        because it's horrifically slow."""
        
        return self._permissions
        
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
    
    def evaluate(self, user, character, rule_set=None, _context=None):
        """Evaluate group ACL rules for the given user and character. _context is used to track
        information through recursive evaluation. ACL and Group evaluation should forward the
        context if one is passed in."""
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
                if self.evaluate(user, character, rule_set='join', _context=_context):
                    return True
            if character in self.request_members:
                if self.evaluate(user, character, rule_set='request', _context=_context):
                    return True
            rules = self.rules
        
        for rule in rules:
            result = rule.evaluate(user, character, _context=_context)
            if result is not None:
                return result
        
        return False  # deny by default

    def cycle_check(self, rules=None, groups_referenced=None):
        if groups_referenced is None:
            groups_referenced = []

        if rules is None:
            self.cycle_check(self.request_rules, groups_referenced)
            self.cycle_check(self.join_rules, groups_referenced)
            self.cycle_check(self.rules, groups_referenced)
            return

        if self.id in groups_referenced:
            raise CyclicGroupReference(list(groups_referenced))
        groups_referenced.append(self.id)

        try:
            for rule in rules:
                if isinstance(rule, ACLGroupMembership):
                    rule.group.cycle_check(groups_referenced=groups_referenced)
        finally:
            id = groups_referenced.pop()
            assert id == self.id

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
        new_self = Group(id=new_name, title=self.title, rules=self.rules, join_rules=self.join_rules, request_rules=self.request_rules,
                        join_members=self.join_members, request_members=self.request_members, requests=self.requests,
                        creator=self.creator, modified=datetime.utcnow, _permissions=self._permissions)

        new_self = new_self.save()

        for other_g in self.get_references():
            print "other group", other_g
            for rule in itertools.chain(other_g.rules, other_g.join_rules, other_g.request_rules):
                if isinstance(rule, ACLGroupMembership) and rule.group.id == self.id:
                    rule.group = new_self
            other_g.save()

        for gc in GroupCategory.objects(members=self):
            gc.members.remove(self)
            gc.members.append(new_self)
            gc.save()

        self.delete()
        return new_self
        
    def get_perm(self, perm_type):
        return getattr(self, perm_type+"_PERM").format(group_id=self.id)
        
    @property
    def view_perm(self):
        return self.get_perm('VIEW')
        
    @property
    def edit_id_perm(self):
        return self.get_perm('EDIT_ID')

    @property
    def edit_title_perm(self):
        return self.get_perm('EDIT_TITLE')

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


signals.pre_save.connect(Group.pre_save, sender=Group)
signals.pre_delete.connect(Group.pre_delete, sender=Group)
