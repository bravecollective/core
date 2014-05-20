# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime, timedelta
from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, EmailField, URLField, DateTimeField, BooleanField, ReferenceField, ListField, IntField

from brave.core.util.signal import update_modified_timestamp
from brave.core.application.signal import trigger_private_key_generation
from brave.core.util.field import PasswordField, IPAddressField
from brave.core.account.model import User


log = __import__('logging').getLogger(__name__)

    
class CharacterBan(EmbeddedDocument):
    """Stores information about character bans."""
    
    meta = dict(
            allow_inheritance = False,
            indexes = [
                    dict(fields=['name'], unique=True),
                    dict(fields=['enabled'])
                ]
        )
        
    # The character this ban is for.
    # Uses a string rather than a reference so users can't get around
    # the blacklist by deleting the banned character or account
    character = StringField(db_field='name')
    
    # The date at which this character was banned.
    date = DateTimeField(db_field='created', default=datetime.utcnow)
    
    # The reason indicates how this character came to be banned.
    # 'direct' means the (overall) ban was invoked against this character in particular.
    # 'account' means the (overall) ban was invoked against the account that owned this character.
    # 'key' means this character was found on the same key as another banned character.
    reason = StringField(db_field='reason', choices=((
            ('direct'),
            ('account'),
            ('key')
        )))
    
    enabled = BooleanField(db_field='enabled', default=True)
    
    
class IPBan(EmbeddedDocument):
    """Stores information about bans against an IP Address."""
    
    meta = dict(
            allow_inheritance = False,
            indexes = [
                    'host',
                    'enabled'
                ]
        )
    
    host = StringField('IP')
    
    # The date at which this character was banned.
    date = DateTimeField(db_field='created', default=datetime.utcnow)
    
    # The reason indicates how this character came to be banned.
    # 'direct' means the (overall) ban was invoked against this IP Address in particular.
    # 'account' means the (overall) ban was invoked against the account that this IP was registered against.
    reason = StringField(db_field='reason', choices=((
            ('direct'),
            ('account')
        )))
        
    enabled = BooleanField(db_field='enabled', default=True)
    
    
class Ban(Document):
    """Holds information about a single ban.
    
    Multiple characters and/or IP addresses can be encompassed in
    one ban object."""
    
    meta = dict(
            allow_inheritance = False,
            indexes = [
                    dict(fields=['creator', 'enabled', 'charCreator'])
                ]
        )
    
    characters = ListField(EmbeddedDocumentField(CharacterBan))
    IPs = ListField(EmbeddedDocumentField(IPBan))
    
    enabled = BooleanField(db_field='enabled', default=True)
    creator = ReferenceField(User, required=True) # TODO: Nullify inverse deletion rule.
    charCreator = StringField(db_field='charCreator', required=True)
    
    
class AuthenticationBlacklist(Document):
    """Blacklist for applications and servers."""
    
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
    
    expires = DateTimeField(db_field='e', default=lambda: datetime.utcnow() + timedelta(minutes=10))
    
    def __repr__(self):
        return 'AuthenticationRequest({0}, {1}, {2}, {3})'.format(self.id, self.application, self.user, self.grant)
