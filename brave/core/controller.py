# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime, timedelta

from web.core import Controller, HTTPMethod, config, session, request
from web.auth import user
from web.core.http import HTTPFound, HTTPNotFound
from web.core.locale import set_lang, LanguageError, _
from marrow.util.convert import boolean
from marrow.util.url import URL

from brave.core import util
from brave.core.util.signal import StartupMixIn
from brave.core.util.predicate import authorize, authenticated
from brave.core.api.model import AuthenticationRequest


log = __import__('logging').getLogger(__name__)


class DeveloperTools(Controller):
    def die(self):
        """Simply explode.  Useful to get the interactive debugger up."""
        1/0
    
    def test(self):
        """Return an HTML/templating scratch pad."""
        return 'brave.core.template.test', dict(data=None)


class AuthorizeHandler(HTTPMethod):
    def ar(self, ar):
        if not session.get('ar', None) == ar:
            session['ar'] = ar
            session.save()
            raise HTTPFound(location='/account/authenticate?redirect=%2Fauthorize%2F{0}'.format(ar))
        
        try:
            return AuthenticationRequest.objects.get(id=ar, user=None, grant=None)
        except AuthenticationRequest.DoesNotExist:
            raise HTTPNotFound()
    
    def get(self, ar):
        from brave.core.application.model import ApplicationGrant
        
        ar = self.ar(ar)
        u = user._current_obj()
        grant = ApplicationGrant.objects(user=u, application=ar.application).first()
        
        if not grant:
            # TODO: We need a 'just logged in' flag in the request.
            
            characters = list(u.characters.order_by('name').all())
            if len(characters):
                default = u.primary or characters[0]
            else:
                return ('brave.core.template.authorize',
                dict(success=False, message=_("This application requires that you have a character connected to your"
                                              " account. Please <a href=\"/key/\">add an API key</a> to your account."),
                     ar=ar))
            return 'brave.core.template.authorize', dict(success=True, ar=ar, characters=characters, default=default)
        
        ngrant = ApplicationGrant(user=u, application=ar.application, mask=grant.mask, expires=datetime.utcnow() + timedelta(days=30), character=grant.character)
        ngrant.save()
        
        ar.user = u
        ar.grant = ngrant
        ar.expires = datetime.utcnow() + timedelta(minutes=10)  # extend to allow time for verification
        ar.save()
        
        r = grant.delete()
        
        target = URL(ar.success)
        target.query.update(dict(token=str(ngrant.id)))
        raise HTTPFound(location=str(target))
    
    def post(self, ar, grant=None, character=None):
        from brave.core.character.model import EVECharacter
        from brave.core.application.model import ApplicationGrant
        
        ar = self.ar(ar)
        u = user._current_obj()
        
        if not grant:
            # Deny access.
            ar.user = u
            ar.grant = None
            ar.expires = datetime.utcnow() + timedelta(minutes=10)  # extend to allow time for verification
            ar.save()
            
            target = URL(ar.failure)
            target.query.update(dict(token=str(ar.id)))
            
            return 'json:', dict(success=True, location=str(target))
        
        try:
            character = EVECharacter.objects.get(owner=u, id=character)
        except EVECharacter.DoesNotExist:
            return 'json:', dict(success=False, message="Unknown character ID.")
        except:
            log.exception("Error loading character.")
            return 'json:', dict(success=False, message="Error loading character.")
        
        # TODO: Non-zero grants.
        grant = ApplicationGrant(user=u, application=ar.application, mask=0, expires=datetime.utcnow() + timedelta(days=30), character=character)
        grant.save()
        
        ar.user = u
        ar.grant = grant
        ar.expires = datetime.utcnow() + timedelta(minutes=10)  # extend to allow time for verification
        ar.save()
        
        target = URL(ar.success)
        target.query.update(dict(token=str(grant.id)))
        return 'json:', dict(success=True, location=str(target))


class RootController(StartupMixIn, Controller):
    account = util.load('account')
    key = util.load('key')
    character = util.load('character')
    application = util.load('application')
    api = util.load('api')
    group = util.load('group')
    admin = util.load('admin')
    
    def __init__(self, *args, **kw):
        super(RootController, self).__init__(*args, **kw)
        
        self.authorize = AuthorizeHandler()  # to avoid gumming up the @authorize decorator
        
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
