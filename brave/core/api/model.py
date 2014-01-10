# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime, timedelta
from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, EmailField, URLField, DateTimeField, BooleanField, ReferenceField, ListField, IntField

from brave.core.util.signal import update_modified_timestamp
from brave.core.application.signal import trigger_private_key_generation
from brave.core.util.field import PasswordField, IPAddressField


log = __import__('logging').getLogger(__name__)


class AuthenticationBlacklist(Document):
    meta = dict(
            allow_inheritance = False,
            indexes = [
                    'scheme',
                    'protocol',
                    'domain',
                    'port'
                ]
        )
    
    scheme = StringField('s')
    protocol = StringField('p')
    domain = StringField('d')
    port = StringField('o')
    
    creator = ReferenceField('User')  # TODO: Nullify inverse deletion rule.


class AuthenticationRequest(Document):
    meta = dict(
            allow_inheritance = False,
            indexes = [
                    dict(fields=['expires'], expireAfterSeconds=0)
                ]
        )
    
    application = ReferenceField('Application', db_field='a')
    user = ReferenceField('User', db_field='u')
    grant = ReferenceField('ApplicationGrant', db_field='g')
    
    success = URLField(db_field='s')
    failure = URLField(db_field='f')
    
    expires = DateTimeField(db_field='e', default=lambda: datetime.utcnow() + timedelta(hours=24, minutes=10))  # TODO: Set this back for prod.
    
    def __repr__(self):
        return 'AuthenticationRequest({0}, {1}, {2}, {3})'.format(self.id, self.application, self.user, self.grant)
