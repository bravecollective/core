# encoding: utf-8

from __future__ import unicode_literals

from itertools import chain
from datetime import datetime, timedelta
from mongoengine import Document, StringField, EmailField, DateTimeField, BooleanField, ReferenceField, ListField
from mongoengine.fields import LongField

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
    
    username = StringField(db_field='u', required=True, unique=True, regex=r'[a-z][a-z0-9_.-]+')
    email = EmailField(db_field='e', required=True, unique=True, regex=r'[^A-Z]+')  # disallow uppercase characters
    password = PasswordField(db_field='p')
    active = BooleanField(db_field='a', default=False)
    confirmed = DateTimeField(db_field='c')
    admin = BooleanField(db_field='d', default=False)
    
    # TODO: Extract into a sub-document and re-name the DB fields.
    rotp = BooleanField(default=False)
    otp = ListField(StringField(max_length=12), default=list)
    
    primary = ReferenceField('EVECharacter')  # "Default" character to use during authz.

    modified = DateTimeField(db_field='m', default=datetime.utcnow)
    seen = DateTimeField(db_field='s')
    host = IPAddressField(db_field='h')
    
    # Python Magic Methods
    
    def __repr__(self):
        return 'User({0}, {1})'.format(self.id, self.username).encode('ascii', 'backslashreplace')
    
    def __unicode__(self):
        return self.username

    @property
    def created(self):
        return self.id.generation_time

    # Related Data Lookups
    
    @property
    def credentials(self):
        from brave.core.key.model import EVECredential
        return EVECredential.objects(owner=self)
    
    @property
    def characters(self):
        from brave.core.character.model import EVECharacter
        return EVECharacter.objects(owner=self)
    
    @property
    def grants(self):
        from brave.core.application.model import ApplicationGrant
        return ApplicationGrant.objects(user=self)
    
    @property
    def attempts(self):
        return LoginHistory.objects(user=self)

    @property
    def recovery_keys(self):
        return PasswordRecovery.objects(user=self)

    # Functions to manage YubiKey OTP

    def addOTP(self, yid):
        yid = yid[:12]
        if yid in self.otp:
            return False
        self.otp.append(yid)
        self.save()
        return True

    def removeOTP(self, yid):
        yid = yid[:12]
        if not yid in self.otp:
            return False
        self.otp.remove(yid)
        self.save()
        return True
    
    def merge(self, other):
        """Consumes other and takes its children."""
        
        other.credentials.update(set__owner=self)
        other.characters.update(set__owner=self)
        
        LoginHistory.objects(user=other).update(set__user=self)
        
        from brave.core.group.model import Group
        from brave.core.application.model import Application, ApplicationGrant
        
        Group.objects(creator=other).update(set__creator=self)
        Application.objects(owner=other).update(set__owner=self)
        ApplicationGrant.objects(user=other).update(set__user=self)
        
        other.delete()


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

class PasswordRecovery(Document):
    meta = dict(
        collection = "PwdRecovery",
        allow_inheritance = False,
        indexes = [
            'user',
            # Automatically delete records as they expire.
            dict(fields=['expires'], expireAfterSeconds=0)
        ]
    )

    user = ReferenceField(User, required=True)
    recovery_key = LongField(db_field='k', required=True)
    expires = DateTimeField(db_field='e', default=lambda: datetime.utcnow() + timedelta(minutes=15))

    @property
    def created(self):
        return self.id.generation_time

    def __repr__(self):
        return 'PasswordRecovery({0}, {1}, {2})'.format(
            self.id.generation_time.isoformat(),
            self.user_id,
            self.recovery_key
        )
