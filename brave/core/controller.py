# encoding: utf-8

from __future__ import unicode_literals

from web.core import Controller
from web.core.locale import set_lang, LanguageError

from brave.core import util
from brave.core.util.signal import StartupMixIn
from brave.core.util.predicate import authorize, authenticated



class RootController(StartupMixIn, Controller):
    account = util.load('account')
    key = util.load('key')
    character = util.load('character')
    application = util.load('application')
    api = util.load('api')
    
    @authorize(authenticated)
    def index(self):
        return 'brave.core.template.dashboard', dict()
    
    def lang(self, lang):
        try:
            set_lang(lang)
        except LanguageError:
            return 'json:', dict(success=False)
        
        return 'json:', dict(success=True)
