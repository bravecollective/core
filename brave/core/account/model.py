# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime, timedelta
from mongoengine import Document, StringField, EmailField, DateTimeField, BooleanField, ReferenceField, ListField

from brave.core.util.signal import update_modified_timestamp
from brave.core.util.field import PasswordField, IPAddressField


@update_modified_timestamp.signal
class User(Document):
    meta = dict(
        collection = 'Users',
        allow_inheritance = False,
        indexes = ['otp'],
    )
    
    # Field Definitions
    
    username = StringField(db_field='u', required=True, unique=True, regex=r'[a-zA-Z][a-zA-Z_.-]+')
    email = EmailField(db_field='e', required=True, unique=True)
    password = PasswordField(db_field='p')
    active = BooleanField(db_field='a', default=False)
    confirmed = DateTimeField(db_field='c')
    admin = BooleanField(db_field='d', default=False)
    otp = ListField(StringField(max_length=12), default=list)
    
    primary = ReferenceField('EVECharacter')  # "Default" character to use during authz.

    modified = DateTimeField(db_field='m', default=datetime.utcnow)
    seen = DateTimeField(db_field='s')
    host = IPAddressField(db_field='h')
    
    # Python Magic Methods
    
    def __repr__(self):
        return 'User({0}, {1})'.format(self.id, self.username).encode('ascii', 'backslashreplace')

    # Related Data Lookups
    
    @property
    def credentials(self, **kw):
        from brave.core.key.model import EVECredential
        return EVECredential.objects(owner=self)
    
    @property
    def characters(self, **kw):
        from brave.core.character.model import EVECharacter
        return EVECharacter.objects(owner=self)


class LoginHistory(Document):
    meta = dict(
            collection = "AuthHistory",
            allow_inheritance = False,
            indexes = [
                    'user',
                    # Automatically delete records as they expire.
                    dict(fields=['expires'], expireAfterSeconds=0)
                ]
        )
    
    user = ReferenceField(User)
    success = BooleanField(db_field='s', default=True)
    location = IPAddressField(db_field='l')
    expires = DateTimeField(db_field='e', default=lambda: datetime.utcnow() + timedelta(days=30))
    
    def __repr__(self):
        return 'LoginHistory({0}, {1}, {2}, {3})'.format(
                self.id.generation_time.isoformat(),
                'PASS' if self.success else 'FAIL',
                self.user_id,
                self.location
            )
