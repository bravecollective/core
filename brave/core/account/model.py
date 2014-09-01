# encoding: utf-8

from __future__ import unicode_literals

from marrow.util.convert import boolean
from datetime import datetime, timedelta
from mongoengine import Document, StringField, EmailField, DateTimeField, BooleanField, ReferenceField, ListField, ValidationError, EmbeddedDocument, EmbeddedDocumentField
from mongoengine.fields import LongField
from yubico import yubico

from brave.core.util.signal import update_modified_timestamp
from brave.core.util.field import PasswordField, IPAddressField
from pyotp import TOTP, random_base32

from web.core import config


class OTP(EmbeddedDocument):
    """Generic OTP class, for saving and managing the various types of OTPs users can add to their account."""
    
    meta = dict(
        allow_inheritance=True,
        indexes=['identifier']
    )
    
    # The 'unique' part of the OTP. This could be an actual identifier (in the case of a yubico OTP) or the secret
    # of the OTP setup.
    identifier = StringField(db_field='i')
    # Whether the OTP is required.
    required = BooleanField(db_field='r', default=True)
    
    def verify(self, response):
        """Validates the response to see if it matches our computed value."""
        raise NotImplementedError
    

class TimeOTP(OTP):
    """OTP sub-class for an RFC 4226 compliant one time password."""
    
    def __init__(self, identifier, *args, **kwargs):
        """Check that the provided identifier is 16 characters. This was done to ensure that the identifier
        field is a StringField across all subclasses, and as far as I know, it is not possible to add additional
        restrictions to a field that is declared in a parent class. Note that the identifier in this case is the
        shared secret."""
        
        if len(identifier) != 16:
            raise ValidationError('The identifier for TimeOTPs must be 16 characters.')
            
        super(TimeOTP, self).__init__(identifier=identifier, *args, **kwargs)
        
    def verify(self, response):
        """Checks response for validity, taking into account the current time."""
        
        response = int(response)
        
        return self.otp.verify(response)
    
    def now(self):
        return self.otp.now()
    
    @property
    def uri(self):
        """Returns the provisioning URI for this OTP object."""
        
        owner = User.objects(otp__identifier=self.identifier).first()
        
        if not owner:
            log.warning("Apparently no one owns the OTP with identifier {0}".format(self.identifier))
            return None
            
        return self.otp.provisioning_uri("Core Auth - " + owner.username) 
            
        
    @property
    def otp(self):
        """Returns the PyOTP TOTP representation of this object. This is used for things such as creating provisioning
        URIs, QR Codes, and verifying user responses."""
        
        return TOTP(self.identifier)
    
    @classmethod
    def create(cls):
        """Creates and returns a new TimeOTP object."""
        otp = cls(identifier=random_base32(), required=True)
        return otp


class YubicoOTP(OTP):
    """OTP sub-class for handling Yubico OTPs registered to user accounts."""
    
    def __init__(self, identifier, *args, **kwargs):
        """Check that the provided identifier is 12 or fewer characters. This was done to ensure that the identifier
        field is a StringField across all subclasses, and as far as I know, it is not possible to add additional
        restrictions to a field that is declared in a parent class."""
        
        if len(identifier) > 12:
            raise ValidationError('The identifier for YubicoOTPs must be 12 or fewer characters.')
            
        super(YubicoOTP, self).__init__(identifier=identifier, *args, **kwargs)
        
    def verify(self, response):
        client = yubico.Yubico(
            config['yubico.client'],
            config['yubico.key'],
            boolean(config.get('yubico.secure', False))
        )
            
        try:
            status = client.verify(response, return_response=True)
        except:
            return False
        
        if not status:
            return False
            
        return True
    
    @classmethod
    def create(cls, yid):
        yid = yid[:12]
        otp = YubicoOTP(identifier=yid, required=True)
        return otp


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
    
    otp = EmbeddedDocumentField(OTP, db_field='o')
    
    primary = ReferenceField('EVECharacter')  # "Default" character to use during authz.

    modified = DateTimeField(db_field='m', default=datetime.utcnow)
    seen = DateTimeField(db_field='s')
    host = IPAddressField(db_field='h')
    
    # Distinguish how we identified the other core accounts as being owned by this one
    # because IP address IDing can cause mis-IDs
    other_accs_char_key = ListField(ReferenceField('User'), db_field='otherAccountsCharKey')
    other_accs_IP = ListField(ReferenceField('User'), db_field='otherAccountsIP')
    
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

    @property
    def otp_required(self):
        return self.otp and self.otp.required
        
    @property
    def tfa_required(self):
        return self.otp and self.otp.required and not isinstance(self.otp, YubicoOTP)

    # Functions to manage OTPs

    def add_otp(self, otp):
        """Adds otp as the user's otp value iff the user has no otp set currently."""
        if not isinstance(otp, OTP):
            return False
        
        if self.otp:
            return False
        
        self.otp = otp
        self.save()
        return True

    def remove_otp(self):
        """Removes the user's OTP, even if it's already been disabled."""
        self.otp = None
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

    def delete(self):

        for c in self.characters:
            c.detach()
            
        self.credentials.delete()
        self.grants.delete()
        self.attempts.delete()
        self.recovery_keys.delete()
        
        dups = set(self.other_accs_char_key)
        
        for other in dups:
            self.remove_duplicate(self, other)
            
        dups = set(self.other_accs_IP)
        
        for other in dups:
            self.remove_duplicate(self, other, IP=True)
        
        super(User, self).delete()
        
    @staticmethod
    def add_duplicate(acc, other, IP=False):
        """Marks other as a duplicate account to this account.
        And marks this account as duplicate to other."""
        
        # If the 2 accounts supplied are the same, do nothing
        if acc.id == other.id:
            return
        
        if not IP:
            if other not in acc.other_accs_char_key:
                acc.other_accs_char_key.append(other)
            if acc not in other.other_accs_char_key:
                other.other_accs_char_key.append(acc)
        else:
            if other not in acc.other_accs_IP:
                acc.other_accs_IP.append(other)
            if acc not in other.other_accs_IP:
                other.other_accs_IP.append(acc)
                
        acc.save()
        other.save()
        
    @staticmethod
    def remove_duplicate(acc, other, IP=False):
        """Removes a duplicate account connection for both accounts."""
        
        # If the 2 accounts supplied are the same, do nothing
        if acc.id == other.id:
            return
        
        if not IP:
            if other in acc.other_accs_char_key:
                acc.other_accs_char_key.remove(other)
            if acc in other.other_accs_char_key:
                other.other_accs_char_key.remove(acc)
        else:
            if other in acc.other_accs_IP:
                acc.other_accs_IP.remove(other)
            if acc in other.other_accs_IP:
                other.other_accs_IP.remove(acc)
                
        acc.save()
        other.save()

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
    # Will throw an exception if the config has a non integer config value
    expires = DateTimeField(db_field='e', default=lambda: datetime.utcnow() + timedelta(days=int(config['core.login_history_days'])))
    
    def __repr__(self):
        return 'LoginHistory({0}, {1}, {2}, {3})'.format(
                self.id.generation_time.isoformat(),
                'PASS' if self.success else 'FAIL',
                self.user.username,
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
            self.user.username,
            self.recovery_key
        )
