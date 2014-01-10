# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime, timedelta

from web.core import Controller, config, session, request
from web.auth import user
from web.core.http import HTTPFound, HTTPNotFound
from web.core.locale import set_lang, LanguageError
from marrow.util.convert import boolean
from marrow.util.url import URL

from brave.core import util
from brave.core.util.signal import StartupMixIn
from brave.core.util.predicate import authorize, authenticated
from brave.core.api.client import API
from brave.core.api.model import AuthenticationRequest


log = __import__('logging').getLogger(__name__)


class DeveloperTools(Controller):
    def die(self):
        """Simply explode.  Useful to get the interactive debugger up."""
        1/0
    
    def test(self):
        """Return an HTML/templating scratch pad."""
        return 'brave.core.template.test', dict(data=None)
    
    def authn(self):
        """Request the API to authenticate a user, see what we get back."""
        
        # To make API calls, we need the API keys.
        # The private key is *our* private key, to sign requests.
        # The public key is the *server's* public key, given after registering your application.
        # We're cheating here so they're one and the same for simplicity.
        # (Generally you'd do this once on startup.)
        from binascii import hexlify, unhexlify
        from hashlib import sha256
        from ecdsa.keys import SigningKey, VerifyingKey
        from ecdsa.curves import NIST256p
        private = SigningKey.from_string(unhexlify(config['api.key']), curve=NIST256p, hashfunc=sha256)
        public = private.get_verifying_key()
        
        # Construct an API instance to get easy attribute-access to the remote functions.
        api = API(config['api.endpoint'], config['api.identity'], private, public)
        
        # We request an authenticated session from the server.
        result = api.authorize(
                success = 'http://localhost:8080/dev/win',
                failure = 'http://localhost:8080/dev/fail'
            )
        
        return 'brave.core.template.test', dict(data=result)


class RootController(StartupMixIn, Controller):
    account = util.load('account')
    key = util.load('key')
    character = util.load('character')
    application = util.load('application')
    api = util.load('api')
    
    def __init__(self, *args, **kw):
        super(RootController, self).__init__(*args, **kw)
        
        if boolean(config.get('debug', False)):
            self.dev = DeveloperTools()
    
    @authorize(authenticated)
    def index(self):
        return 'brave.core.template.dashboard', dict()
    
    def lang(self, lang):
        try:
            set_lang(lang)
        except LanguageError:
            return 'json:', dict(success=False)
        
        return 'json:', dict(success=True)
    
    def authorize(self, ar, grant=None, character=None):
        from brave.core.character.model import EVECharacter
        from brave.core.application.model import ApplicationGrant
        
        # TODO: The updates in this should be atomic update-if-not-changed.
        
        # TODO: This security needs a bit of work.
        # We need a 'just logged in' flag in the request.
        if not session.get('ar', None) == ar:
            session['ar'] = ar
            session.save()
            raise HTTPFound(location='/account/authenticate?redirect=%2Fauthorize%2F{0}'.format(ar))
        
        ar = AuthenticationRequest.objects.get(id=ar)
        
        if ar.user or ar.grant:
            raise HTTPNotFound()
        
        if request.method == 'POST':
            if not grant:
                ar.user = user._current_obj()
                ar.grant = None
                ar.expires = datetime.utcnow() + timedelta(minutes=10)  # extend to allow time for verification
                ar.save()
                
                target = URL(ar.failure)
                target.query.update(dict(token=str(ar.id)))
                return 'json:', dict(success=True, location=str(target))
            
            try:
                character = EVECharacter.objects.get(owner=user._current_obj(), id=character)
            except:
                log.exception("Error loading character.")
                return 'json:', dict(success=False, message="Unknown character ID.")
            
            user_ = user._current_obj()
            
            # TODO: Non-zero grants.
            grant = ApplicationGrant(user=user_, application=ar.application, mask=0, expires=datetime.utcnow() + timedelta(days=30), character=character)
            grant.save()
            
            ar.user = user_
            ar.grant = grant
            ar.expires = datetime.utcnow() + timedelta(minutes=10)  # extend to allow time for verification
            ar.save()
            
            target = URL(ar.success)
            target.query.update(dict(token=str(grant.id)))
            return 'json:', dict(success=True, location=str(target))
        
        characters = list(user.characters.order_by('name').all())
        
        default = characters[0]  # TODO: Allow this to be user-defined.
        
        return 'brave.core.template.authorize', dict(ar=ar, characters=characters, default=default)
    
    
