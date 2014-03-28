# encoding: utf-8

from marrow.util.bunch import Bunch
from web.auth import authenticate, deauthenticate
from web.core import Controller, HTTPMethod, request, config
from web.core.http import HTTPFound, HTTPSeeOther, HTTPForbidden
from web.core.locale import _

from brave.core.account.model import User
from brave.core.account.form import authenticate as authenticate_form, register as register_form
from brave.core.account.authentication import lookup

from yubico import yubico, yubico_exceptions
from marrow.util.convert import boolean

import re

log = __import__('logging').getLogger(__name__)


class Authenticate(HTTPMethod):
    def get(self, redirect=None):
        if redirect is None:
            referrer = request.referrer
            redirect = '/' if not referrer or referrer.endswith(request.script_name) else referrer

        form = authenticate_form(dict(redirect=redirect))
        return 'brave.core.account.template.signin', dict(form=form)

    def post(self, identity, password, remember=False, redirect=None):
        #Ensures that the provided identity is lowercase if it's an email or username, but leaves it alone if it's an OTP
        if('@' in identity or len(identity) != 44): 
            identity = identity.lower()
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
        
        #Make sure that the provided email address is a valid form for an email address
        #TODO: Support IDNs and make RFC 822 compliant
        emailSearch = re.search('[a-zA-Z0-9\.\+]+@[a-zA-Z0-9\.\+]+\.[a-zA-Z0-9]+', data.email)
        if emailSearch == None:
            return 'json:', dict(success=False, message=_("Invalid email address provided."), data=data)
         
        #Prevents Mongodb validation check from hanging thread, plus all tlds are at least 2 characters.
        tldSearch = re.findall('\.[a-zA-Z0-9]+', data.email)
        tld = tldSearch.pop()
        #tld includes the leading '.'
        if len(tld) < 3:
            return 'json:', dict(success=False, message=_("Invalid email address provided."), data=data)
        
        #Ensures that the provided username and email are lowercase
        user = User(data.username.lower(), data.email.lower(), active=True)
        user.password = data.password
        user.save()
        
        authenticate(data.username.lower(), data.password)
        
        return 'json:', dict(success=True, location="/")

class Settings(HTTPMethod):
    def get(self, admin=False):
        if admin and not is_administrator:
            raise HTTPNotFound()

        return 'brave.core.account.template.settings', dict()

    def post(self, **post):
        try:
            data = Bunch(post)
        except Exception as e:
            if config.get('debug', False):
                raise
            return 'json:', dict(success=False, message=_("Unable to parse data."), data=post, exc=str(e))

        query = dict(active=True)
        query[b'username'] = data.id

        user = User.objects(**query).first()

        if data.form == "changepassword":
            if data.passwd != data.passwd1:
                return 'json:', dict(success=False, message=_("New passwords do not match."), data=data)

            if len(data.passwd) > 100:
                return 'json:', dict(success=False, message=_("Password over 100 charactor limit"), data=data)

            if isinstance(data.old, unicode):
                data.old = data.old.encode('utf-8')
                #print(data.old)

            if not User.password.check(user.password, data.old):
                return 'json:', dict(success=False, message=_("Old password incorrect."), data=data)

            user.password = data.passwd
            user.save()
        elif data.form == "addotp":
            if isinstance(data.password, unicode):
                data.password = data.password.encode('utf-8')

            identifier = data.otp
            client = yubico.Yubico(
                config['yubico.client'],
                config['yubico.key'],
                boolean(config.get('yubico.secure', False))
            )

            if not User.password.check(user.password, data.password):
                return 'json:', dict(success=False, message=_("Password incorrect."), data=data)

            try:
                status = client.verify(identifier, return_response=True)
            except:
                return 'json:', dict(success=False, message=_("Failed to contact YubiCloud."), data=data)

            if not status:
                return 'json:', dict(success=False, message=_("Failed to verify key."), data=data)

            if not User.addOTP(user, identifier[:12]):
                return 'json:', dict(success=False, message=_("YubiKey already exists."), data=data)
        elif data.form == "removeotp":
            identifier = data.otp

            if not User.removeOTP(user, identifier[:12]):
                return 'json:', dict(success=False, message=_("YubiKey invalid."), data=data)

        elif data.form == "configureotp":
            if isinstance(data.password, unicode):
                data.password = data.password.encode('utf-8')
            rotp = True if 'rotp' in data else False

            if not User.password.check(user.password, data.password):
                return 'json:', dict(success=False, message=_("Password incorrect."), data=data)
            
            user.rotp = rotp
            user.save()
			
        #Handle the user attempting to delete their account
        elif data.form == "deleteaccount":
            if isinstance(data.passwd, unicode):
                data.passwd = data.passwd.encode('utf-8')
             
            #Make the user enter their username so they know what they're doing.
            if not user.username == data.username.lower():
                return 'json:', dict(success=False, message=_("Username incorrect."), data=data)
        
            #Check whether the user's supplied password is correct
            if not User.password.check(user.password, data.passwd):
                return 'json:', dict(success=False, message=_("Password incorrect."), data=data)
                
            #Make them type "delete" exactly
            if not data.confirm == "delete":
                return 'json:', dict(success=False, message=_("Delete was either misspelled or not lowercase."), data=data)
            
            #Delete the user account and then deauthenticate the browser session
            user.delete()
            deauthenticate()
            
            #Redirect user to the root of the server instead of the settings page
            return 'json:', dict(success=True, location="/")
			
        else:
            return 'json:', dict(success=False, message=_("Form does not exist."), location="/")
        
        return 'json:', dict(success=True, location="/account/settings")


class AccountController(Controller):
    authenticate = Authenticate()
    register = Register()
    settings = Settings()
    
    def exists(self, **query):
        query.pop('ts', None)
        
        if set(query.keys()) - {'username', 'email'}:
            raise HTTPForbidden()
        
        count = User.objects.filter(**{str(k): v for k, v in query.items()}).count()
        return 'json:', dict(available=not bool(count), query={str(k): v for k, v in query.items()})
    
    def deauthenticate(self):
        deauthenticate()
        raise HTTPSeeOther(location='/')

