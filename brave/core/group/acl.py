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
    
    def evaluate(self, user, character):
        raise NotImplementedError()


class ACLList(ACLRule):
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
        return character.alliance.identifier in self.ids
    
    def evaluate(self, user, character):
        if getattr(self, 'evaluate_' + self.KINDS[self.kind].lower())(user, character):
            return self.grant
        
        return None  # this acl rule doesn't match or is not applicable
