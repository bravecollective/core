# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime
from collections import OrderedDict
from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, EmailField, URLField, DateTimeField, BooleanField, ReferenceField, ListField, IntField

from brave.core.util.signal import update_modified_timestamp


log = __import__('logging').getLogger(__name__)


class ACLRule(EmbeddedDocument):
    meta = dict(
            abstract = True,
            allow_inheritance = True,
        )
    
    # ACL rules evaluate to None (doesn't apply), False (deny access), and True (allow access)
    # the fist ACLRule for a group that evaluates non-None is the accepted result
    grant = BooleanField(db_field='g', default=False)  # paranoid default
    inverse = BooleanField(db_field='z', default=False)  # pass/fail if the rule *doesn't* match
    
    def evaluate(self, user, character):
        raise NotImplementedError()
    
    def __repr__(self):
        return "{0}({1}{2})".format(
                self.__class__.__name__,
                '!' if self.inverse else '',
                'grant' if self.grant else 'deny'
            )


class ACLList(ACLRule):
    """Grant or deny access based on the character's ID, corporation ID, or alliance ID."""
    
    KINDS = OrderedDict([
            ('c', "Character"),
            ('o', "Corporation"),
            ('a', "Alliance")
        ])
    
    kind = StringField(db_field='k', choices=KINDS.items())
    ids = ListField(IntField(), db_field='i')
    
    def evaluate_character(self, user, character):
        return character.identifier in self.ids
    
    def evaluate_corporation(self, user, character):
        return character.corporation.identifier in self.ids
    
    def evaluate_alliance(self, user, character):
        return character.alliance and character.alliance.identifier in self.ids
    
    def evaluate(self, user, character):
        if getattr(self, 'evaluate_' + self.KINDS[self.kind].lower())(user, character):
            return None if self.inverse else self.grant
        
        # this acl rule doesn't match or is not applicable
        return self.grant if self.inverse else None
    
    def __repr__(self):
        return "ACLList({0}{1} {2} {3!r})".format(
                '!' if self.inverse else '',
                'grant' if self.grant else 'deny',
                self.KINDS[self.kind],
                self.ids
            )


class ACLKey(ACLRule):
    """Grant or deny access based on the character's key type."""
    
    KINDS = OrderedDict([
            ('Account', "Account"),
            ('Character', "Character"),
            ('Corporation', "Corporation")
        ])
    
    kind = StringField(db_field='k', choices=KINDS.items())
    
    def evaluate(self, user, character):
        for key in character.credentials:
            if key.kind == self.kind:
                return None if self.inverse else self.grant
        
        return self.grant if self.inverse else None
    
    def __repr__(self):
        return "ACLKey({0}{1} {2})".format(
                '!' if self.inverse else '',
                'grant' if self.grant else 'deny',
                self.KINDS[self.kind]
            )


class ACLTitle(ACLRule):
    """Grant or deny access based on the character's corporate title."""
    
    titles = ListField(StringField(), db_field='t')
    
    def evaluate(self, user, character):
        if set(character.titles) & set(self.titles):
            return None if self.inverse else self.grant
        
        # this acl rule doesn't match or is not applicable
        return self.grant if self.inverse else None
    
    def __repr__(self):
        return "ACLTitle({0}{1} {2!r})".format(
                '!' if self.inverse else '',
                'grant' if self.grant else 'deny',
                self.titles
            )


class ACLRole(ACLRule):
    """Grant or deny access based on the character's corporate role."""
    
    roles = ListField(StringField(), db_field='t')
    
    def evaluate(self, user, character):
        if set(character.roles) & set(self.roles):
            return None if self.inverse else self.grant
        
        # this acl rule doesn't match or is not applicable
        return self.grant if self.inverse else None
    
    def __repr__(self):
        return "ACLRole({0}{1} {2!r})".format(
                '!' if self.inverse else '',
                'grant' if self.grant else 'deny',
                self.roles
            )


class ACLMask(ACLRule):
    """Grant or deny access based on having a key capable of evaluating the given mask."""
    
    mask = IntField(db_field='m')
    
    def evaluate(self, user, character):
        mask = self.mask
        
        for cred in character.credentials:
            if cred.mask & mask == mask:
                return None if self.inverse else self.grant
        
        return self.grant if self.inverse else None
    
    def __repr__(self):
        return "ACLMask({0}{1} {2})".format(
                '!' if self.inverse else '',
                'grant' if self.grant else 'deny',
                self.mask
            )
