# encoding: utf-8

from __future__ import unicode_literals

from time import time, sleep
from datetime import datetime, timedelta

import web.core
from mongoengine import Document, StringField, EmailField, DateTimeField, BooleanField, ReferenceField, ListField
from yubico import yubico, yubico_exceptions

from adam.auth.model.signals import update_modified_timestamp
from adam.auth.model.fields import PasswordField, IPAddressField


@update_modified_timestamp.signal
class User(Document):
    meta = dict(
        collection = "Users",
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
    
    primary = ReferenceField('EVECharacter')

    modified = DateTimeField(db_field='m', default=datetime.utcnow)
    seen = DateTimeField(db_field='s')
    
    # Python Magic Methods
    
    def __repr__(self):
        return 'User({0}, {1})'.format(self.id, self.username).encode('ascii', 'backslashreplace')

    # Related Data Lookups
    
    @property
    def credentials(self, **kw):
        from adam.auth.model.eve import EVECredential
        return EVECredential.objects(owner=self)
    
    @property
    def characters(self, **kw):
        from adam.auth.model.eve import EVECharacter
        return EVECharacter.objects(owner=self)
    
    # WebCore Authentication
    
    @classmethod
    def authenticate(cls, identifier, password):
        query = dict(active=True)
        
        if isinstance(password, unicode):
            password = password.encode('utf8')
        
        if '@' in identifier:
            query[b'email'] = identifier
        elif len(identifier) == 44:
            query[b'otp'] = identifier[:12]
        else:
            query[b'username'] = identifier
        
        user = cls.objects(**query).first()
        
        ts = time()
        if not user or not User.password.check(user.password, password):
            if user:
                LoginHistory(user, False, web.core.request.remote_addr).save()
            
            # Prevent basic timing attacks; always take at least one second to process.
            sleep(max(min(1 - (time() - ts), 0), 1))
            
            return None
        
        # Validate OTP
        if 'otp' in query:
            client = yubico.Yubico(
                    web.core.config['yubico.client'],
                    web.core.config['yubico.key'],
                    True if web.core.config.get('yubico.secure', False) == 'True' else False
                )
            
            try:
                status = client.verify(identifier, return_response=True)
            except:
                return None
            
            if not status:
                return None
        
        user.update(set__seen=datetime.utcnow())
        LoginHistory(user, True, web.core.request.remote_addr).save()
        
        return user.id, user
    
    @classmethod
    def lookup(cls, identifier):
        user = cls.objects(id=identifier).first()
        
        if user:
            user.update(set__seen=datetime.utcnow())
        
        return user


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
