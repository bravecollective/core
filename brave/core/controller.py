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
        try:
            return AuthenticationRequest.objects.get(id=ar, user=None, grant=None)
        except AuthenticationRequest.DoesNotExist:
            raise HTTPNotFound()
    
    @authenticate
    def get(self, ar=None):
        from brave.core.application.model import ApplicationGrant

        if ar is None:
            raise HTTPBadRequest()
        
        ar = self.ar(ar)
        u = user._current_obj()
        grant = ApplicationGrant.objects(user=u, application=ar.application).first()
        
        if not grant:
            # TODO: We need a 'just logged in' flag in the request.

            if u.person.banned(ar.application.short):
                return ('brave.core.template.authorize',
                dict(success=False, message=_("You have been banned from using this application. Please see the ban " +
                                                "search page for more details."), ar=ar))

            characters = list(u.characters.order_by('name').all())
            if not len(characters):
                return ('brave.core.template.authorize',
                dict(success=False, message=_("This application requires that you have a character connected to your"
                                              " account. Please <a href=\"/key/\">add an API key</a> to your account."),
                     ar=ar))

            if not u.has_permission(ar.application.authorize_perm):
                return ('brave.core.template.authorize',
                dict(success=False, message=_("You do not have permission to use this application."), ar=ar))

            chars = []
            for c in characters:
                if c.credential_for(ar.application.mask.required):
                    chars.append(c)
            
            if not chars:
                return ('brave.core.template.authorize',
                dict(success=False, message=_("This application requires an API key with a mask of <a href='/key/mask/{0}'>{0}</a> or better, please add an API key with that mask to your account.".format(ar.application.mask.required)),
                     ar=ar))
            
            chars = [c for c in chars
                     if (c.has_verified_key or
                         config['core.require_recommended_key'].lower() == 'false')]
                    
            if chars:
                default = u.primary if u.primary in chars else chars[0]
            else:
                return ('brave.core.template.authorize',
                    dict(success=False, message=_(
                        "You do not have any API keys on your account which match the requirements for this service. "
                        "Please add an {1} API key with a mask of <a href='/key/mask/{0}'>{0}</a> or better to your account."
                        .format(config['core.recommended_key_mask'], config['core.recommended_key_kind'])),
                        ar=ar))

            if ar.application.require_all_chars:
                default = 'all'
                     

            return 'brave.core.template.authorize', dict(
                success=True,
                ar=ar,
                characters=chars,
                default=default,
                only_one_char=ar.application.auth_only_one_char,
            )

            return 'brave.core.template.authorize', dict(success=True, ar=ar, characters=chars, default=default)

        if u.person.banned(ar.application.short):
            return ('brave.core.template.authorize',
                dict(success=False, message=_("You have been banned from using this application. Please see the ban " +
                                                "search page for more details."), ar=ar))


        ngrant = ApplicationGrant(user=u, application=ar.application, _mask=grant._mask, expires=datetime.utcnow() + timedelta(days=ar.application.expireGrantDays), chars=grant.chars, all_chars=grant.all_chars)
        ngrant.save()
        
        ar.user = u
        ar.grant = ngrant
        ar.expires = datetime.utcnow() + timedelta(minutes=10)  # extend to allow time for verification
        ar.save()
        
        r = grant.delete()
        
        target = URL(ar.success)
        target.query.update(dict(token=str(ngrant.id)))
        raise HTTPFound(location=str(target))
    
    # **kwargs as jQuery form encodes 'characters' to 'characters[]'
    @authenticate
    def post(self, ar, grant=None, all_chars=False, **kwargs):
        from brave.core.character.model import EVECharacter
        from brave.core.application.model import ApplicationGrant
        
        ar = self.ar(ar)
        u = user._current_obj()

        if u.person.banned(ar.application.short):
            return ('brave.core.template.authorize',
                dict(success=False, message=_("You have been banned from using this application. Please see the ban " +
                                                "search page for more details."), ar=ar))
        
        if not grant:
            # Deny access.
            ar.user = u
            ar.grant = None
            ar.expires = datetime.utcnow() + timedelta(minutes=10)  # extend to allow time for verification
            ar.save()
            
            target = URL(ar.failure)
            target.query.update(dict(token=str(ar.id)))
            
            return 'json:', dict(success=True, location=str(target))
        
        characters = []

        if all_chars.lower() == 'true':
            all_chars = True
        else:
            all_chars = False
        
        if not all_chars and ar.application.require_all_chars:
            return 'json:', dict(success=False, message="This application requires access to all of your characters.")
        
        # Require at least one character
        if 'characters[]' not in kwargs and not all_chars:
            return 'json:', dict(success=False, message="Select at least one character.")
        character_ids = kwargs['characters[]'] if 'characters[]' in kwargs else []
        # Handle only one character being authorized
        if character_ids and not isinstance(character_ids, list):
            character_ids = [character_ids]
        for character in character_ids:
            try:
                characters.append(EVECharacter.objects.get(owner=u, id=character))
            except EVECharacter.DoesNotExist:
                return 'json:', dict(success=False, message="Unknown character ID.")
            except:
                log.exception("Error loading character.")
                return 'json:', dict(success=False, message="Error loading character.")
        
        # TODO: Add support for 'optional' masks
        mask = ar.application.mask.required
        grant = ApplicationGrant(user=u, application=ar.application, _mask=mask, expires=datetime.utcnow() + timedelta(days=ar.application.expireGrantDays), chars=characters if characters else u.characters, all_chars=all_chars)
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
    ban = util.load('ban')
    kiu = util.load('kiu')

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
        return 'brave.core.account.template.accountdetails', dict(
            area='admin' if user.admin else 'account',
            account=user._current_obj(),
        )

    def lang(self, lang):
        try:
            set_lang(lang)
        except LanguageError:
            return 'json:', dict(success=False)
        
        return 'json:', dict(success=True)
