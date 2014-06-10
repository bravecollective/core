# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime, timedelta
from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, EmailField, URLField, DateTimeField, BooleanField, ReferenceField, ListField, IntField

from brave.core.character.model import EVECharacter
from brave.core.account.model import User


log = __import__('logging').getLogger(__name__)


class CharacterBan(EmbeddedDocument):
    """Stores information about character bans."""
    
    meta = dict(
        allow_inheritance=False,
        indexes=[
            'n',
            '_enabled'
        ]
    )
        
    # The character this ban is for.
    character = ReferenceField(EVECharacter, db_field='n', required=True)
    
    # The date at which this character was banned.
    date = DateTimeField(db_field='d', default=datetime.utcnow)
    
    # The reason indicates how this character came to be banned.
    # 'direct' means the (overall) ban was invoked against this character in particular.
    # 'account' means the (overall) ban was invoked against the account that owned this character.
    # 'key' means this character was found on the same key as another banned character.
    reason = StringField(db_field='r', choices=((
        ('direct'),
        ('account'),
        ('key')
    )))
    
    _enabled = BooleanField(db_field='e', default=True)
    
    def enable(self, user):
        """Enables this ban."""
        
        # Don't spam logs with 'fake' enables.
        if not self._enabled:
            log.info("User %s enabled CharacterBan against %s (%s).".format((user.username, self.character, self.id)))
            self._enabled = True
            
    def disable(self, user):
        """Disables this ban."""
        
        # Don't spam logs with 'fake' disables.
        if self._enabled:
            log.info("User %s disabled ban against %s (%s).".format((user.username, self.host, self.id)))
            self._enabled = False
            
    def __repr__(self):
        return "CharacterBan({0}) {1} Enabled: {2}".format(str(self.id), self.character, self._enabled)
    
    
class IPBan(EmbeddedDocument):
    """Stores information about bans against an IP Address."""
    
    meta = dict(
        allow_inheritance=False,
        indexes=[
            'host',
            '_enabled'
        ]
    )
    
    host = StringField(db_field='IP', required=True)
    
    # The date at which this character was banned.
    date = DateTimeField(db_field='d', default=datetime.utcnow)
    
    # The reason indicates how this character came to be banned.
    # 'direct' means the (overall) ban was invoked against this IP Address in particular.
    # 'account' means the (overall) ban was invoked against the account that this IP was registered against.
    reason = StringField(db_field='r', choices=((
        ('direct'),
        ('account')
    )))
        
    _enabled = BooleanField(db_field='e', default=True)
    
    def enable(self, user):
        """Enables this ban."""
        
        # Don't spam logs with 'fake' enables.
        if not self._enabled:
            log.info("User %s enabled IPban against %s (%s).".format((user.username, self.host, self.id)))
            self._enabled = True
            
    def disable(self, user):
        """Disables this ban."""
        
        # Don't spam logs with 'fake' disables.
        if self._enabled:
            log.info("User %s disabled ban against %s (%s).".format((user.username, self.host, self.id)))
            self._enabled = False
            
    def __repr__(self):
        return "IPBan({0}) {1} Enabled: {2}".format(str(self.id), self.host, self._enabled)
    
    
class Ban(Document):
    """Holds information about a single ban.
    
    Multiple characters and/or IP addresses can be encompassed in
    one ban object."""
    
    meta = dict(
        allow_inheritance=False,
        collection = 'Bans',
        indexes=[
            'creator',
            '_enabled',
            'charCreator'
        ]
    )
    
    characters = ListField(EmbeddedDocumentField(CharacterBan), db_field='c', default=list)
    IPs = ListField(EmbeddedDocumentField(IPBan), default=list)
    
    _enabled = BooleanField(db_field='e', default=True)
    creator = ReferenceField(User, required=True, db_field='a', reverse_delete_rule='NULLIFY')
    
    # Store the character that created the ban separately in case of account deletion.
    charCreator = ReferenceField(EVECharacter, db_field='cc', required=True)
    
    # Require a reason for the top-level ban. This enables better accountability.
    reason = StringField(db_field='r', required=True)
    
    # The date at which this Ban was created.
    date = DateTimeField(db_field='d', default=datetime.utcnow)
    
    def enable(self, user):
        """Enables this ban."""
        
        # Don't spam logs with 'fake' enables.
        if not self._enabled:
            log.info("User %s enabled ban %s.".format((user.username, self.id)))
            self._enabled = True
        
        # Enable all child bans (even if this ban was previously enabled)
        for b in self.characters:
            b.enable(user)
                
        for b in self.IPs:
            b.enable(user)
            
    def disable(self, user):
        """Disables this ban."""
        
        # Don't spam logs with 'fake' disables.
        if self._enabled:
            log.info("User %s disabled ban %s.".format((user.username, self.id)))
            self._enabled = False
        
        # Disable all child bans (even if this ban was previously disabled)
        for b in self.characters:
            b.disable(user)
                
        for b in self.IPs:
            b.disable(user)
            
    def ban_character(self, character, reason):
        # Check if the character has already been banned in this ban
        if self in Ban.objects(characters__character=character):
            return
             
        if not character:
            return
             
        c = CharacterBan()
        c.character = character
        c.reason = reason
        
        self.characters.append(c)
        self.save()
        
    def ban_ip(self, ip, reason):
        # Check if the IP has already been banned in this ban
        if self in Ban.objects(IPs__host=ip):
            return
            
        if not ip:
            return
            
        i = IPBan()
        i.host = ip
        i.reason = reason
            
        self.IPs.append(i)
        self.save()
            
    def initializeBan(self, user=None, character=None, ip=None, reason=None, creator=None):
        """Creates a new ban that bans the specified arguments, along with any other characters and IP addresses
            affiliated with the account. user must be of the type User, and character must be an EVECharacter.
            Alternative to using __init__, which is also called when MongoEngine returns items from the DB and thus
            leads to interesting complications."""
        
        # A reason and a creator must be supplied.
        if not reason or not creator:
            self.delete()
            return
        
        self.reason = reason
        self.creator = creator
        
        # Make sure the creator is a Document
        if not isinstance(creator, Document):
            return
            
        self.charCreator = creator.primary if creator.primary else creator.characters[0]
        
        # Ban all IP addresses and characters associated with the user that owns this character.
        if character:
            # Invalid argument.
            if not isinstance(character, EVECharacter):
                return
                
            # Ban the character supplied.
            self.ban_character(character, 'direct')
            
            for c in character.owner.characters:
                # Check if this character is on the same key (and thus EVE account) as the directly banned character.
                for cred in c.credentials:
                    if cred in character.credentials:
                        self.ban_character(c, 'key')
                
                # Ban all the other characters on the account.
                self.ban_character(c, 'account')
            
            # Ban the IP address associated with the account of the banned character.
            if character.owner:
                self.ban_ip(character.owner.host, 'account')
        
        # Ban all IP addresses and characters associated with this IP address.
        if ip:
            # If this IP is already banned, change it's reason to direct.
            if self in Ban.objects(IPs__host=ip):
                i = self.IPs.objects(host=ip).first()
                i.reason = 'direct'
                i.save()
                
            self.ban_ip(ip, 'direct')
            
            # If there are any accounts associated with this IP, ban all of their characters.
            if len(User.objects(host=ip)):
                users = User.objects(host=ip)
                for u in users:
                    for c in u.characters:
                        self.ban_character(c, 'account')
                    
        # Ban all characters and IP addresses associated with this user.
        if user:
            if not isinstance(user, User):
                return
            
            for c in user.characters:
                self.ban_character(c, 'account')
            
            # Only ban this user's IP if it's not already banned in this ban.
            self.ban_ip(user.host, 'account')
            
    def __repr__(self):
        return ("Ban({0}); Characters({1}); IPs({2}); Enabled: {3}".format(str(self.id), ",".join(self.characters),
                ",".join(self.IPs), self._enabled))
