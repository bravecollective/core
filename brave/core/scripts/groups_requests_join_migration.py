from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, EmailField, URLField, DateTimeField, BooleanField, ReferenceField, ListField, IntField
from brave.core.group.acl import ACLRule
from brave.core.character.model import EVECharacter
from datetime import datetime
from brave.core.permission.model import Permission

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

    join_members = ListField(StringField(), db_field='jmn', default=list)
    request_members = ListField(StringField(), db_field='rmn', default=list)
    requests = ListField(StringField(), db_field='rln', default=list)

    join_members_depr = ListField(ReferenceField(EVECharacter), db_field='jm', default=list)
    request_members_depr = ListField(ReferenceField(EVECharacter), db_field='rm', default=list)
    requests_depr = ListField(ReferenceField(EVECharacter), db_field='rl', default=list)
    
    creator = ReferenceField('User', db_field='c')
    modified = DateTimeField(db_field='m', default=datetime.utcnow)
    _permissions = ListField(ReferenceField(Permission), db_field='p')

def migrate_groups(dry_run=True):
    m = 0
    for g in Group.objects:
        g.join_members = [c.name for c in g.join_members_depr]
        g.request_members = [c.name for c in g.request_members_depr]
        g.requests = [c.name for c in g.requests_depr]
        if not dry_run:
            g.save()
        m += 1
    print "{} groups migrated.".format(m)