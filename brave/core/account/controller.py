# encoding: utf-8

from marrow.util.bunch import Bunch
from marrow.mailer.validator import EmailValidator
from web.auth import authenticate as web_authenticate, deauthenticate, user
from web.core import Controller, HTTPMethod, request, config, session
from web.core.http import HTTPFound, HTTPSeeOther, HTTPForbidden, HTTPNotFound, HTTPBadRequest
from web.core.locale import _
from mongoengine import ValidationError, NotUniqueError

from brave.core.account.model import User, PasswordRecovery
from brave.core.account.form import authenticate as authenticate_form, register as register_form, \
    recover as recover_form, reset_password as reset_password_form
from brave.core.account.authentication import lookup_email, send_recover_email
from brave.core.person.model import Person
from brave.core.util.predicate import is_administrator, authenticate

from yubico import yubico
from marrow.util.convert import boolean

import zxcvbn
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

class AccountIndex(HTTPMethod):
    def get(self, redirect=None):
        from web.auth import user
        return AccountInterface(user.id).get()

class Authenticate(HTTPMethod):
    def get(self, redirect=None):
        if redirect is None:
            referrer = request.referrer
            redirect = '/' if not referrer or referrer.endswith(request.script_name) else referrer

        form = authenticate_form(dict(redirect=redirect))
        return 'brave.core.account.template.signin', dict(form=form)

    def post(self, identity, password, remember=False, redirect=None):

        # Prevent users from specifying their session IDs (Some user-agents were sending null ids, leading to users
        # authenticated with a session id of null
        session.regenerate_id()

        # First try with the original input
        success = web_authenticate(identity, password)

        if not success:
            # Try lowercase if it's an email or username, but not if it's an OTP
            if '@' in identity or len(identity) != 44:
                success = web_authenticate(identity.lower(), password)

        if not success:
            if request.is_xhr:
                return 'json:', dict(success=False, message=_("Invalid user name or password."))

            return self.get(redirect)

        # User is global banned.
        if user.person.banned():
            temp = user.id
            deauthenticate()
            return 'json:', dict(success=True, location='/account/banned?user=' + str(temp))

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
            user = lookup_email(email.lower())
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
            user = lookup_email(data.email.lower())
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

        #If the password isn't strong enough, reject it
        if(zxcvbn.password_strength(data.password).get("score") < int(config['core.required_pass_strength'])):
            return 'json:', dict(success=False, message=_("Password provided is too weak. please add more characters, or include lowercase, uppercase, and special characters."), data=data)

        #set new password
        user = recovery.user
        user.password = data.password
        user.save()

        #remove recovery key
        recovery.delete()

        web_authenticate(user.username, data.password)

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
        v = EmailValidator()
        email = data.email
        email, err = v.validate(email)
        if err:
            return 'json:', dict(success=False, message=_("Invalid email address provided."), data=data)
        
        #If the password isn't strong enough, reject it
        if(zxcvbn.password_strength(data.password).get("score") < int(config['core.required_pass_strength'])):
            return 'json:', dict(success=False, message=_("Password provided is too weak. please add more characters, or include lowercase, uppercase, and special characters."), data=data)
        
        #Ensures that the provided username and email are lowercase
        user = User(data.username.lower(), data.email.lower(), active=True)
        user.password = data.password
        try:
            user.save()
        except ValidationError:
            return 'json:', dict(success=False, message=_("Invalid email address or username provided."), data=data)
        except NotUniqueError:
            return 'json:', dict(success=False, message=_("Either the username or email address provided is "
                                                          "already taken."), data=data)
        
        web_authenticate(user.username, data.password)
        
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

        query_user = User.objects(**query).first()
        if query_user.id != user.id:
            raise HTTPForbidden

        if data.form == "changepassword":
            passwd_ok, error_msg = _check_password(data.passwd, data.passwd1)

            if not passwd_ok:
                return 'json:', dict(success=False, message=error_msg, data=data)

            if isinstance(data.old, unicode):
                data.old = data.old.encode('utf-8')

            if not User.password.check(user.password, data.old):
                return 'json:', dict(success=False, message=_("Old password incorrect."), data=data)

            #If the password isn't strong enough, reject it
            if(zxcvbn.password_strength(data.passwd).get("score") < int(config['core.required_pass_strength'])):
                return 'json:', dict(success=False, message=_("Password provided is too weak. please add more characters, or include lowercase, uppercase, and special characters."), data=data)

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
            log.info("User %s authorized the deletion of their account.", user)
            user.delete()
            deauthenticate()
            
            #Redirect user to the root of the server instead of the settings page
            return 'json:', dict(success=True, location="/")
            
        #Handle the user attempting to change the email address associated with their account
        elif data.form == "changeemail":
            if isinstance(data.passwd, unicode):
                data.passwd = data.passwd.encode('utf-8')
        
            #Check whether the user's supplied password is correct
            if not User.password.check(user.password, data.passwd):
                return 'json:', dict(success=False, message=_("Password incorrect."), data=data)

            #Check that the two provided email addresses match
            if not data.newEmail.lower() == data.newEmailConfirm.lower():
                return 'json:', dict(success=False, message=_("Provided email addresses do not match."), data=data)
            
            #Make sure that the provided email address is a valid form for an email address
            v = EmailValidator()
            email = data.newEmail
            email, err = v.validate(email)
            if err:
                return 'json:', dict(success=False, message=_("Invalid email address provided."), data=data)
                
            #Make sure that the new email address is not already taken
            count = User.objects.filter(**{"email": data.newEmail.lower()}).count()
            if not count == 0:
                return 'json:', dict(success=False, message=_("The email address provided is already taken."), data=data)
       
            #Change the email address in the database and catch any email validation exceptions that mongo throws
            user.email = data.newEmail.lower()
            try:
                user.save()
            except ValidationError:
                return 'json:', dict(success=False, message=_("Invalid email address provided."), data=data)
            except NotUniqueError:
                return 'json:', dict(success=False, message=_("The email address provided is already taken."), data=data)
        
        #Handle the user attempting to merge 2 accounts together
        elif data.form == "mergeaccount":
            if isinstance(data.passwd, unicode):
                data.passwd = data.passwd.encode('utf-8')
                
            if isinstance(data.passwd2, unicode):
                data.passwd2 = data.passwd2.encode('utf-8')
                
            #Make the user enter their username so they know what they're doing.
            if user.username != data.username.lower() and user.username != data.username:
                return 'json:', dict(success=False, message=_("First username incorrect."), data=data)
                
            #Check whether the user's supplied password is correct
            if not User.password.check(user.password, data.passwd):
                return 'json:', dict(success=False, message=_("First password incorrect."), data=data)
                
            #Make sure the user isn't trying to merge their account into itself.
            if data.username.lower() == data.username2.lower():
                return 'json:', dict(success=False, message=_("You can't merge an account into itself."), data=data)
                
            #Make the user enter the second username so we can get the User object they want merged in.
            if not User.objects(username=data.username2.lower()) and not User.objects(username=data.username2):
                return 'json:', dict(success=False, message=_("Unable to find user by second username."), data=data)
                
            other = User.objects(username=data.username2).first()
            if not other:
                other = User.objects(username=data.username2.lower()).first()
                
            #Check whether the user's supplied password is correct
            if not User.password.check(other.password, data.passwd2):
                return 'json:', dict(success=False, message=_("Second password incorrect."), data=data)
                
            #Make them type "merge" exactly
            if data.confirm != "merge":
                return 'json:', dict(success=False, message=_("Merge was either misspelled or not lowercase."), data=data)
                
            log.info("User %s merged account %s into %s.", user.username, other.username, user.username)
            user.merge(other)
            
            #Redirect user to the root of the server instead of the settings page
            return 'json:', dict(success=True, location="/")
            
        else:
            return 'json:', dict(success=False, message=_("Form does not exist."), location="/")
        
        return 'json:', dict(success=True, location="/account/settings")


class AccountInterface(HTTPMethod):
    """Handles the individual user pages."""
    
    @authenticate
    def __init__(self, userID):
        super(AccountInterface, self).__init__()
        
        try:
            self.user = User.objects.get(id=userID)
        except User.DoesNotExist:
            raise HTTPNotFound()
        except ValidationError:
            # Handles improper objectIDs
            raise HTTPNotFound()

        if self.user.id != user.id and not user.has_permission(self.user.view_perm):
            raise HTTPNotFound()
    
    @authenticate
    def get(self):
        return 'brave.core.account.template.accountdetails', dict(
            area='admin' if user.admin else 'account',
            account=self.user,
        )


class AccountController(Controller):
    authenticate = Authenticate()
    register = Register()
    settings = Settings()
    recover = Recover()
    index = AccountIndex()

    def banned(self, user):
        bans = []

        user = User.objects(id=user).first()
        # We only show enabled bans in the search window to users without permission
        for b in user.person.bans:
            if b.enabled:
                bans.append(b)
                continue

        return 'brave.core.account.template.banned', dict(
                success = True,
                results=bans,
            )
    
    def exists(self, **query):
        query.pop('ts', None)
        
        if set(query.keys()) - {'username', 'email'}:
            raise HTTPForbidden()
        
        count = User.objects.filter(**{str(k): v.lower() for k, v in query.items()}).count()
        return 'json:', dict(available=not bool(count), query={str(k): v for k, v in query.items()})
        
    def entropy(self, **query):
        # Remove the timestamp
        query.pop('ts', None)
        
        # Make sure the user provides only a password
        if set(query.keys()) - {'password'}:
            raise HTTPForbidden()
        
        password = query.get("password")
        strong = False
        
        # If the password has a score of greater than core.required_pass_strength, allow it
        if(zxcvbn.password_strength(password).get("score") >= int(config['core.required_pass_strength'])):
            strong = True
        
        return 'json:', dict(approved=strong, query={str(k): v for k, v in query.items()})
    
    def deauthenticate(self):
        deauthenticate()
        raise HTTPSeeOther(location='/')
        
    def __lookup__(self, user=None, *args, **kw):
        if not user:
            raise HTTPBadRequest
        request.path_info_pop()  # We consume a single path element.
        return AccountInterface(user), args
