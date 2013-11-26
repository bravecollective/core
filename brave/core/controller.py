# encoding: utf-8

from __future__ import unicode_literals

from web.core import Controller, config
from web.core.locale import set_lang, LanguageError
from marrow.util.convert import boolean

from brave.core import util
from brave.core.util.signal import StartupMixIn
from brave.core.util.predicate import authorize, authenticated
from brave.core.api.client import API



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
    
