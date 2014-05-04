# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime, timedelta
from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, EmailField, URLField, DateTimeField, BooleanField, ReferenceField, ListField, IntField

from brave.core.util.signal import update_modified_timestamp
from brave.core.application.signal import trigger_private_key_generation


log = __import__('logging').getLogger(__name__)



class ApplicationKeys(EmbeddedDocument):
    meta = dict(
            allow_inheritance = False,
        )
    
    public = StringField(db_field='u')  # Application public key.
    private = StringField(db_field='r')  # Server private key.


class ApplicationMasks(EmbeddedDocument):
    meta = dict(
            allow_inheritance = False,
        )
    
    required = IntField(db_field='r', default=0)
    optional = IntField(db_field='o', default=0)
    
    def __repr__(self):
        return 'Masks({0}, {1})'.format(self.required, self.optional)


@update_modified_timestamp.signal
@trigger_private_key_generation.signal
class Application(Document):
    meta = dict(
            collection = 'Applications',
            allow_inheritance = False,
            indexes = [],
            ordering = ('name', )
        )
    
    # Field Definitions
    
    name = StringField(db_field='n')
    description = StringField(db_field='d')
    site = URLField(db_field='s')
    contact = EmailField(db_field='c')
    
    key = EmbeddedDocumentField(ApplicationKeys, db_field='k', default=lambda: ApplicationKeys())
    
    mask = EmbeddedDocumentField(ApplicationMasks, db_field='m', default=lambda: ApplicationMasks())
    groups = ListField(StringField(), db_field='g', default=list)
    
    # TODO: "Development"-only applications.
    
    owner = ReferenceField('User', db_field='o')
    
    # Related Data
    
    @property
    def grants(self):
        return ApplicationGrant.objects(application=self)
    
    # Python Magic Methods
    
    def __repr__(self):
        return 'Application({0}, "{1}", {2})'.format(self.id, self.name, self.mask)
    
    def __unicode__(self):
        return self.name


class ApplicationGrant(Document):
    meta = dict(
            collection = 'Grants',
            allow_inheritance = False,
            indexes = [
                    dict(fields=['expires'], expireAfterSeconds=0)
                ],
        )

    user = ReferenceField('User', db_field='u')
    application = ReferenceField(Application, db_field='a')
    
    character = ReferenceField('EVECharacter', db_field='c')
    _mask = IntField(db_field='m', default=0)
    
    immutable = BooleanField(db_field='i', default=False)  # Onboarding is excempt from removal by the user.
    expires = DateTimeField(db_field='x')  # Default grant is 30 days, some applications exempt.  (Onboarding, Jabber, TeamSpeak, etc.)
    
    # Python Magic Methods
    
    @property
    def mask(self):
        """Returns a Key Mask object instead of just the integer."""
        if self._mask:
            return EVECharacterKeyMask(self._mask)
        return None
        
    @mask.setter
    def mask(self, value):
        """Sets the value of the Key Mask"""
        self._mask = value
    
    def __repr__(self):
        return 'Grant({0}, "{1}", "{2}", {3})'.format(self.id, self.user, self.application, self.mask).encode('ascii', 'backslashreplace')
