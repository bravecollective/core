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

        if boolean(config.get('debug', False)):
            self.dev = DeveloperTools()

    def authorize(self, ar=None, *args, **kw):
        from brave.core.api.auth.controller import AuthorizeController

        return AuthorizeController.core.index(ar=ar, *args, **kw)
    
    @authenticate
    def index(self):
        return 'brave.core.template.dashboard', dict()
    
    def lang(self, lang):
        try:
            set_lang(lang)
        except LanguageError:
            return 'json:', dict(success=False)
        
        return 'json:', dict(success=True)
