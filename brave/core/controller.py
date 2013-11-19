# encoding: utf-8

from web.auth import authenticate, deauthenticate
from web.core import Controller, HTTPMethod, request, config
from web.core.locale import set_lang, LanguageError
from web.core.http import HTTPFound, HTTPSeeOther, HTTPForbidden
from web.core.locale import _

from marrow.mailer import Mailer
from marrow.util.bunch import Bunch

from adam.auth.controller.key import KeyController
from adam.auth.controller.character import CharacterController


from brave.core import util
from brave.core.util.signal import StartupMixIn
from brave.core.util.predicate import authorize, authenticated



class RootController(Controller, StartupMixIn):
    account = util.load('user', 'AccountController')
    key = util.load('key', 'KeyController')
    character = util.load('character', 'CharacterController')
    
    character = CharacterController()
    
    @authorize(authenticated)
    def index(self):
        return "adam.auth.template.dashboard", dict()
    
    def lang(self, lang):
        try:
            set_lang(lang)
        except LanguageError:
            return 'json:', dict(success=False)
        
        return 'json:', dict(success=True)
