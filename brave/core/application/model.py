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
    
    # This is the short name of the application, which is used for permissions. Must be lowercase.
    short = StringField(db_field='p', unique=True, regex='[a-z]+', required=True)
    
    key = EmbeddedDocumentField(ApplicationKeys, db_field='k', default=lambda: ApplicationKeys())
    
    mask = EmbeddedDocumentField(ApplicationMasks, db_field='m', default=lambda: ApplicationMasks())
    groups = ListField(StringField(), db_field='g', default=list)
    development = BooleanField(db_field='dev')
    # Number of days that grants for this application should last.
    expireGrantDays = IntField(db_field='e', default=30)
    
    # This field indicates whether the application requires access to every character on the authorizing user's account.
    require_all_chars = BooleanField(db_field='a', default=False)
    auth_only_one_char = BooleanField(db_field='one', default=False)
    
    owner = ReferenceField('User', db_field='o')
    
    # Permissions
    EDIT_PERM = 'core.application.edit.{app_short}'
    CREATE_PERM = 'core.application.create'
    AUTHORIZE_PERM = 'core.application.authorize.{app_short}'
    
    # Related Data
    
    @property
    def grants(self):
        return ApplicationGrant.objects(application=self)
    
    # Python Magic Methods
    
    def __repr__(self):
        return 'Application({0}, "{1}", {2})'.format(self.id, self.name, self.mask)
    
    def __unicode__(self):
        return self.name
    
    def get_perm(self, perm_type):
        return getattr(self, perm_type+"_PERM").format(app_short=self.short)
    
    @property
    def edit_perm(self):
        return self.get_perm('EDIT')
    
    @property
    def authorize_perm(self):
        return self.get_perm('AUTHORIZE')


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
    
    # Deprecated
    character = ReferenceField('EVECharacter', db_field='c')
    
    chars = ListField(ReferenceField('EVECharacter'), db_field='chars', required=True)
    all_chars = BooleanField(db_field='b', default=False)
    _mask = IntField(db_field='m', default=0)
    
    immutable = BooleanField(db_field='i', default=False)  # Onboarding is excempt from removal by the user.
    expires = DateTimeField(db_field='x')  # Default grant is 30 days, some applications exempt.  (Onboarding, Jabber, TeamSpeak, etc.)
    
    # Python Magic Methods
    
    @property
    def characters(self):
        if self.all_chars:
            return self.user.characters
        
        return self.chars
    
    @property
    def default_character(self):
        """This is used for backwards compatibility for old single character grants."""
        if self.character:
            return self.character
        
        for c in self.characters:
            if c == c.owner.primary:
                return c
        
        return self.characters[0]
    
    @property
    def mask(self):
        """Returns a Key Mask object instead of just the integer."""
        from brave.core.util.eve import EVECharacterKeyMask
        
        if self._mask:
            return EVECharacterKeyMask(self._mask)
        return None
        
    @mask.setter
    def mask(self, value):
        """Sets the value of the Key Mask"""
        self._mask = value

    @classmethod
    def remove_grants_for_character(cls, character):
        """Removes the character from all Application Grants, removing the ability for application to access
        the character's data; and forcing the user to reauthorize that character to any applications they wish
        to use it on. Expected use cases include when a character gets detached from a user, and when a character
        no longer has a key with valid requirements to meet an already authorized application."""

        for grant in cls.objects(character=character):
            grant.delete()
    
    def __repr__(self):
        return 'Grant({0}, "{1}", "{2}", {3})'.format(self.id, self.user, self.application, self.mask).encode('ascii', 'backslashreplace')

    def remove_character(self, character):
        """Removes the given character from the list of characters this grant applies to.

        If there are no other characters for this grant, the grant is removed.
        """

        if self.all_chars:
            # If the grant is for all of the user's characters, we cannot simply remove a single
            # character. For the moment, we'll lie and say we did. This is *definitely* not the
            # right solution though. Maybe we should return a bool, or throw an exception that
            # callers must handle?
            # TODO figure out what to really do here
            return

        if len(self.characters) == 1:
            self.delete()
        else:
            self.characters.remove(character)
            self.save()
