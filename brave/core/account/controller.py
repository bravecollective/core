# encoding: utf-8

from marrow.util.bunch import Bunch
from web.auth import authenticate, deauthenticate
from web.core import Controller, HTTPMethod, request, config
from web.core.http import HTTPFound, HTTPSeeOther, HTTPForbidden
from web.core.locale import _

from brave.core.account.model import User, PasswordRecovery
from brave.core.account.form import authenticate as authenticate_form, register as register_form, \
    recover as recover_form, reset_password as reset_password_form
from brave.core.account.authentication import lookup_email, send_recover_email

from yubico import yubico
from marrow.util.convert import boolean

import re

log = __import__('logging').getLogger(__name__)


def _check_password(passwd1, passwd2):
    """checks the passed passwords for equality and length
    (could be extended to add minimal length, complexity, ...)

    Returns a Tuple, the first value is a Boolean that is True,
    if the password is ok, the second value is the error message,
    should it not be ok
    """
    #check for empty password
    if not passwd1:
        return False, _("Please enter a password")
    if passwd1 != passwd2:
        return False, _("New passwords do not match.")
    if len(passwd2) > 100:
        return False, _("Password over 100 character limit")
    return True, None


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


class Recover(HTTPMethod):
    @staticmethod
    def __get_recovery(email, recovery_key):
        if not email:
            return None
        user = lookup_email(email)
        if not user:
            return None
        recovery = PasswordRecovery.objects(user=user, recovery_key=recovery_key).first()
        return recovery

    def get(self, redirect=None, **get):
        if redirect is None:
            referrer = request.referrer
            redirect = '/' if not referrer or referrer.endswith(request.script_name) else referrer
        try:
            data = Bunch(reset_password_form.native(get)[0])
        except Exception as e:
            if config.get('debug', False):
                raise
            raise HTTPFound(location='/') # Todo redirect to recover with error message

        if not data.recovery_key:  # no key passed, so show email entry
            form = recover_form(dict(redirect=redirect))
            button_label = _("Recover")
        else:
            form = reset_password_form(dict(email=data.email, recovery_key=data.recovery_key))
            button_label = _("Set Password")

        return "brave.core.account.template.recover", dict(form=form, button_label=str(button_label))

    def post(self, **post):
        recovery_key = post.get("recovery_key")
        if recovery_key is None:
            return self.__post_email(**post)
        else:
            return self.__post_recovery(**post)

    def __post_email(self, **post):
        try:
            data = Bunch(recover_form.native(post)[0])
        except Exception as e:
            if config.get('debug', False):
                raise
            return 'json:', dict(success=False, message=_("Unable to parse data."), data=post, exc=str(e))

        user = lookup_email(data.email)
        if not user:
            # FixMe: possibly do send success any way, to prevent email address confirmation
            #   - would be necessary for register as well
            return 'json:', dict(success=False, message=_("Unknown email."), data=post)
        send_recover_email(user)
        return 'json:', dict(success=True,
                             message=_("Recovery e-mail sent - "
                                       "please follow the instructions in that mail to restore your password"))

    def __post_recovery(self, **post):
        try:
            data = Bunch(reset_password_form.native(post)[0])
        except Exception as e:
            if config.get('debug', False):
                raise
            return 'json:', dict(success=False, message=_("Unable to parse data."), data=post, exc=str(e))
        recovery = self.__get_recovery(data.email, data.recovery_key)
        if not recovery:
            return 'json:', dict(success=False, message=_("Sorry that recovery link has already expired"),
                                 location="/account/recover")
        passwd_ok, error_msg = _check_password(data.password, data.pass2)
        if not passwd_ok:
            return 'json:', dict(success=False, message=error_msg)

        #set new password
        user = recovery.user
        user.password = data.password
        user.save()

        #remove recovery key
        recovery.delete()

        authenticate(user.username, data.password)

        return 'json:', dict(success=True, message=_("Password changed, forwarding ..."), location="/")


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
            passwd_ok, error_msg = _check_password(data.password, data.pass2)

            if not passwd_ok:
                return 'json:', dict(success=False, message=error_msg, data=data)

            if isinstance(data.old, unicode):
                data.old = data.old.encode('utf-8')

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
    recover = Recover()
    
    def exists(self, **query):
        query.pop('ts', None)
        
        if set(query.keys()) - {'username', 'email'}:
            raise HTTPForbidden()
        
        count = User.objects.filter(**{str(k): v for k, v in query.items()}).count()
        return 'json:', dict(available=not bool(count), query={str(k): v for k, v in query.items()})
    
    def deauthenticate(self):
        deauthenticate()
        raise HTTPSeeOther(location='/')

