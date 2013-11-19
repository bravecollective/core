# encoding: utf-8

from marrow.util.bunch import Bunch
from web.auth import authenticate, deauthenticate
from web.core import Controller, HTTPMethod, request, config
from web.core.http import HTTPFound, HTTPSeeOther, HTTPForbidden
from web.core.locale import _

from brave.core.account.model import User
from brave.core.account.form import authenticate as authenticate_form, register as register_form


log = __import__('logging').getLogger(__name__)


class Authenticate(HTTPMethod):
    def get(self, redirect=None):
        if redirect is None:
            referrer = request.referrer
            redirect = '/' if not referrer or referrer.endswith(request.script_name) else referrer

        form = authenticate_form(dict(redirect=redirect))
        return 'brave.core.account.template.signin', dict(form=form)

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
        return "brave.core.account.template.signup", dict(form=form)

    def post(self, **post):
        try:
            data = Bunch(register_form.native(post)[0])
        except Exception as e:
            if config.get('debug', False):
                raise
            return 'json:', dict(success=False, message=_("Unable to parse data."), data=post, exc=str(e))
        
        if not data.username or not data.email or not data.password or data.password != data.pass2:
            return 'json:', dict(success=False, message=_("Missing data or passwords do not match."), data=data)
        
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
