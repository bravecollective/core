# encoding: utf-8

from __future__ import unicode_literals

import os

from binascii import hexlify
from datetime import datetime, timedelta

from web.core import Controller, HTTPMethod, config, session, request, response
from web.auth import user
from web.core.http import HTTPBadRequest, HTTPFound, HTTPNotFound
from web.core.locale import set_lang, LanguageError, _
from marrow.util.convert import boolean
from marrow.util.url import URL

from brave.core import util
from brave.core.util.signal import StartupMixIn
from brave.core.util.predicate import authorize, authenticate
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
    
    def get(self, ar=None):
        from brave.core.application.model import ApplicationGrant

        if ar is None:
            raise HTTPBadRequest()
        
        ar = self.ar(ar)
        u = user._current_obj()
        grant = ApplicationGrant.objects(user=u, application=ar.application).first()
        
        if not grant:
            # TODO: We need a 'just logged in' flag in the request.
            
            characters = list(u.characters.order_by('name').all())
            if not len(characters):
                return ('brave.core.template.authorize',
                dict(success=False, message=_("This application requires that you have a character connected to your"
                                              " account. Please <a href=\"/key/\">add an API key</a> to your account."),
                     ar=ar))
            chars = []
            for c in characters:
                if c.credential_for(ar.application.mask.required):
                    chars.append(c)
            if chars:
                default = u.primary if u.primary in chars else chars[0]
            else:
                return ('brave.core.template.authorize',
                dict(success=False, message=_("This application requires an API key with a mask of <a href='/key/mask/{0}'>{0}</a> or better, please add an API key with that mask to your account.".format(ar.application.mask.required)),
                     ar=ar))
            return 'brave.core.template.authorize', dict(success=True, ar=ar, characters=chars, default=default)
        
        ngrant = ApplicationGrant(user=u, application=ar.application, mask=grant.mask, expires=datetime.utcnow() + timedelta(days=ar.application.expireGrantDays), character=grant.character)
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
        
        # TODO: Add support for 'optional' masks
        mask = ar.application.mask.required
        grant = ApplicationGrant(user=u, application=ar.application, _mask=mask, expires=datetime.utcnow() + timedelta(days=ar.application.expireGrantDays), character=character)
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

    def __call__(self, req):
        if req.method not in ('GET', 'HEAD'):
            self.check_csrf()
        if not request.cookies.get('csrf'):
            response.set_cookie('csrf', hexlify(os.urandom(16)))

        return super(RootController, self).__call__(req)

    def check_csrf(self):
        # portions of the application explicitly opted out of CSRF protection.
        if request.path_info_peek() == 'api':
            return

        if request.headers.get('X-CSRF'):
            # the browser prevents sites from sending custom HTTP
            # headers to another site but allows sites to send custom HTTP
            # headers to themselves using XMLHttpRequest
            #  - http://www.adambarth.com/papers/2008/barth-jackson-mitchell-b.pdf
            return

        # TODO: if we ever want to support normal in-browser forums, accpet a form field containing
        # the token
        raise HTTPBadRequest
    
    def __init__(self, *args, **kw):
        super(RootController, self).__init__(*args, **kw)
        
        self.authorize = AuthorizeHandler()  # to avoid gumming up the @authorize decorator
        
        if boolean(config.get('debug', False)):
            self.dev = DeveloperTools()
    
    @authenticate
    def index(self):
        return 'brave.core.template.dashboard', dict()
    
    def lang(self, lang):
        try:
            set_lang(lang)
        except LanguageError:
            return 'json:', dict(success=False)
        
        return 'json:', dict(success=True)
