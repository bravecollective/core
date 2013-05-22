# encoding: utf-8

from web.auth import authenticate, deauthenticate
from web.core import Controller, HTTPMethod, request, config
from web.core.locale import set_lang, LanguageError
from web.core.http import HTTPFound, HTTPSeeOther, HTTPForbidden
from web.core.locale import _

from marrow.mailer import Mailer
from marrow.util.bunch import Bunch

import adam.auth.util
from adam.auth.model.authentication import User
from adam.auth.form import authenticate as authenticate_form, register as register_form
from adam.auth.util.predicate import authorize, authenticated

from adam.auth.controller.key import KeyController


class Authenticate(HTTPMethod):
    def get(self, redirect=None):
        if redirect is None:
            referrer = request.referrer
            redirect = '/' if not referrer or referrer.endswith(request.script_name) else referrer

        form = authenticate_form(dict(redirect=redirect))
        return "adam.auth.template.signin", dict(form=form)

    def post(self, identity, password, remember=False, redirect=None):
        if not authenticate(identity, password):
            if request.is_xhr:
                return 'json:', dict(success=False, message=_("Invalid user name or password."))

            return self.get(redirect)

        if request.is_xhr:
            return 'json:', dict(success=True, location=redirect or '/')

        raise HTTPFound(location=redirect or '/')


class Register(HTTPMethod):
    def get(self, redirect=None):
        if redirect is None:
            referrer = request.referrer
            redirect = '/' if not referrer or referrer.endswith(request.script_name) else referrer

        form = register_form(dict(redirect=redirect))
        return "adam.auth.template.signup", dict(form=form)

    def post(self, **post):
        try:
            data = Bunch(register_form.native(post)[0])
        except Exception as e:
            if config.get('debug', False):
                raise
            return 'json:', dict(success=False, message="Unable to parse data.", data=post, exc=str(e))
        
        if not data.username or not data.email or not data.password or data.password != data.pass2:
            return 'json:', dict(success=False, message="Missing data?", data=data)
        
        user = User(data.username, data.email, active=True)
        user.password = data.password
        user.save()
        
        authenticate(data.username, data.password)
        
        return 'json:', dict(success=True, location="/")


class AccountController(Controller):
    authenticate = Authenticate()
    register = Register()
    
    def exists(self, **query):
        query.pop('ts', None)
        
        if set(query.keys()) - {'username', 'email'}:
            raise HTTPForbidden()
        
        count = User.objects.filter(**{str(k): v for k, v in query.items()}).count()
        return 'json:', dict(available=not bool(count), query={str(k): v for k, v in query.items()})
    
    def deauthenticate(self):
        deauthenticate()
        raise HTTPSeeOther(location='/')


class RootController(Controller):
    account = AccountController()
    key = KeyController()
    
    def __init__(self):
        """Perform some startup work, like configuring the mail interface."""
        super(RootController, self).__init__()
        
        adam.auth.util.mail = Mailer(Bunch(config).mail)
        adam.auth.util.mail.start()
    
    @authorize(authenticated)
    def index(self):
        return "adam.auth.template.dashboard", dict()
    
    def lang(self, lang):
        try:
            set_lang(lang)
        except LanguageError:
            return 'json:', dict(success=False)
        
        return 'json:', dict(success=True)
