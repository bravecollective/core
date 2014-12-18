from brave.core.util.predicate import authenticate
from brave.core.character.model import EVECharacter
from brave.core.application.model import ApplicationGrant
from brave.core.api.auth.model import AuthorizationMethod
from brave.core.api.auth.oauth2 import OAuth2AuthorizationCode

from web.core.locale import _
from web.core import Controller, HTTPMethod, config, request
from web.auth import user
from web.core.http import HTTPBadRequest, HTTPFound, HTTPNotFound


log = __import__('logging').getLogger(__name__)


class AuthorizeHandler(HTTPMethod):

    def __init__(self, auth_method=AuthorizationMethod):
        self.auth_method = auth_method
        super(AuthorizeHandler, self).__init__()

    @authenticate
    def get(self, *args, **kw):
        """We've just had the client redirect the user-agent to us trying to get authorization, so we need to
        authenticate the user (handled by the decorator), verify that the application can request authorizations using
        the specified authorization method, and verify that they're eligible to authorize the application."""

        app = self.auth_method.get_application(request, *args, **kw)
        u = user._current_obj()

        self.auth_method.pre_authorize(u, app, request, *args, **kw)

        grant = ApplicationGrant.objects(user=u, application=app).first()
        if grant:
            raise HTTPFound(location=self.auth_method.authenticate(u, app, request, grant, *args, **kw))

        if not app:
            raise HTTPBadRequest("Application not found, please ensure you're providing the correct credentials for the"
                                 " given authorization method.")

        if not self.auth_method.short in app.auth_methods:
            raise HTTPBadRequest("Application is not permitted to request authorization using this authorization"
                                 " method.")

        characters = list(u.characters.order_by('name').all())
        if not len(characters):
            return ('brave.core.template.authorize',
            dict(success=False, message=_("This application requires that you have a character connected to your"
                                          " account. Please <a href=\"/key/\">add an API key</a> to your account."),
                    ))

        if not u.has_permission(app.authorize_perm):
            return ('brave.core.template.authorize',
            dict(success=False, message=_("You do not have permission to use this application.")))

        chars = []
        for c in characters:
            if c.credential_for(app.mask.required):
                chars.append(c)

        if not chars:
            return ('brave.core.template.authorize',
            dict(success=False, message=_("This application requires an API key with a mask of <a href='/key/mask/{0}'>{0}</a> or better, please add an API key with that mask to your account.".format(app.mask.required)),
                ))

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
                    ))

        if app.require_all_chars:
            default = 'all'

        return 'brave.core.template.authorize', dict(
            success=True,
            application=app,
            characters=chars,
            default=default,
            only_one_char=app.auth_only_one_char,
        )

    @authenticate
    def post(self, grant=None, all_chars=False, *args, **kw):

        u = user._current_obj()
        app = self.auth_method.get_application(request, *args, **kw)

        if not grant:
            self.auth_method.deny_authorize(u, app, request)

        characters = []

        if all_chars.lower() == 'true':
            all_chars = True
        else:
            all_chars = False

        if not all_chars and app.require_all_chars:
            return 'json:', dict(success=False, message="This application requires access to all of your characters.")

        # Require at least one character
        if 'characters[]' not in kw and not all_chars:
            return 'json:', dict(success=False, message="Select at least one character.")
        character_ids = kw['characters[]'] if 'characters[]' in kw else []
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

        return self.auth_method.authorize(u, app, request, characters, all_chars, *args, **kw)


class AuthMethodController(Controller):
    """This is the generic Controller for AuthorizationMethods. It should be instantiated with the AuthorzationMethod as
    an argument, and wil handle all of the AuthorizationMethods HTTP requests."""

    def __init__(self, auth_method=AuthorizationMethod):
        self.auth_method = auth_method

    def __default__(self, method=None, *args, **kw):
        if method not in self.auth_method.additional_methods:
            raise HTTPNotFound()

        return getattr(self.auth_method, method)(*args, **kw)

    def index(self, *args, **kw):
        return AuthorizeHandler(self.auth_method)(*args, **kw)

class AuthorizeController(Controller):
    """Authorization Methods Go Here."""
    oauth2 = AuthMethodController(OAuth2AuthorizationCode)
