from brave.core.api.auth.model import AuthorizationMethod
from brave.core.application.model import Application, ApplicationGrant
from brave.core.character.model import EVECharacter

from datetime import datetime, timedelta
from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, EmailField, URLField, DateTimeField, BooleanField, ReferenceField, ListField, IntField
from oauthlib.oauth2 import RequestValidator
from web.core.http import HTTPBadRequest
from web.core import session
from oauthlib.oauth2 import WebApplicationServer, FatalClientError, OAuth2Error
import ast


log = __import__('logging').getLogger(__name__)


class OAuthValidator(RequestValidator):

    @staticmethod
    def verify_http_basic(request):
        from brave.core.api.util import parse_http_basic

        id, secret = parse_http_basic(request)

        if not id or not secret:
            return False

        client = OAuthValidator.verify_id_and_secret(id, secret)

        if not client:
            return False

        request.client = client
        return client

    @staticmethod
    def verify_http_attributes(request):
        if not hasattr(request, 'client_id') or not hasattr(request, 'client_secret'):
            return False

        client = OAuthValidator.verify_id_and_secret(request.client_id, request.client_secret)

        if not client:
            return False

        request.client = client
        return client


    @staticmethod
    def verify_id_and_secret(client_id, client_secret):
        try:
            app = Application.objects.get(id=client_id)
        except Application.DoesNotExist:
            return False

        # Prevent timing attacks against the client secret
        # We could also try getting the application from MongoDB with the secret as an attribute, but not sure
        # if that would protect against timing attacks.

        value = True

        for p, k in zip(client_secret, app.oauth2ac.client_secret):
            if p != k:
                value = False

        if not value:
            return False

        return app

    @staticmethod
    def authenticate_client(request, *args, **kwargs):
        # HTTPBasic Authentication
        if 'Authorization' in request.headers:
            log.debug("HTTPAuthorization Header Detected.")
            return OAuthValidator.verify_http_basic(request)
        # GET or POST attributes
        if hasattr(request, 'client_id') and hasattr(request, 'client_secret'):
            log.debug("Client Credentials in args detected.")
            return OAuthValidator.verify_http_attributes(request)

        return False


    @staticmethod
    def authenticate_client_id(request, *args, **kwargs):
        # At the moment we only support confidential clients.
        return False

    @staticmethod
    def client_authentication_required(request, *args, **kwargs):
        # At the moment we only support confidential clients.
        return True

    @staticmethod
    def confirm_redirect_uri(client_id, code, redirect_uri, client, *args, **kwargs):
        if redirect_uri != client.oauth2ac.redirect_uri:
            return False

        return True

    @staticmethod
    def get_default_redirect_uri(client_id, request, *args, **kwargs):
        return request.client.oauth2ac.redirect_uri

    @staticmethod
    def get_default_scopes(client_id, request, *args, **kwargs):
        return None

    @staticmethod
    def get_original_scopes(refresh_token, request, *args, **kwargs):
        try:
            grant = OAuth2ApplicationGrant.objects.get(refresh_token=refresh_token, application=request.client)
        except OAuth2ApplicationGrant.DoesNotExist:
            return False

        return grant.characters

    @staticmethod
    def invalidate_authorization_code(client_id, code, request, *args, **kwargs):
        try:
            ar = AuthorizationCode.objects.get(code=code)
        except AuthorizationCode.DoesNotExist:
            return

        ar.delete()
        return

    @staticmethod
    def is_within_original_scope(request_scopes, refresh_token, request, *args, **kwargs):
        try:
            grant = OAuth2ApplicationGrant.objects.get(refresh_token=refresh_token, application=request.client)
        except OAuth2ApplicationGrant.DoesNotExist:
            return False

        return all(c in grant.characters for c in request_scopes)

    @staticmethod
    def revoke_token(token, token_type_hint, request, *args, **kwargs):
        if token_type_hint == "access_token":
            try:
                grant = OAuth2ApplicationGrant.objects.get(access_token=token)
            except OAuth2ApplicationGrant.DoesNotExist:
                return

            grant.access_token = None
        elif token_type_hint == "refresh_token":
            try:
                grant = OAuth2ApplicationGrant.objects.get(refresh_token=token)
            except OAuth2ApplicationGrant.DoesNotExist:
                return

            grant.refresh_token = None

    @staticmethod
    def rotate_refresh_token(request):
        return True

    @staticmethod
    def save_authorization_code(client_id, code, request, *args, **kwargs):
        ar = AuthorizationCode(code=code['code'], application=request.client, user=request.user,
                               redirect_uri=request.redirect_uri, scopes=request.scopes, state=request.state)
        ar.save()
        return request.client.oauth2ac.redirect_uri

    @staticmethod
    def save_bearer_token(token, request, *args, **kwargs):
        all_chars = "all_chars" in request.scopes
        chars = [EVECharacter.objects.get(name=c.replace("&", " ")) for c in (request.scopes if not all_chars else [q.name for q in request.user.characters])]

        grant = OAuth2ApplicationGrant(user=request.user, _mask=request.client.mask.required, application=request.client,
                                 expires=datetime.utcnow()+timedelta(days=request.client.expireGrantDays),
                                 access_token=token['access_token'],
                                 refresh_token=token['refresh_token'] if 'refresh_token' in token else None,
                                 chars=chars, all_chars=all_chars)
        grant.save()
        return request.client.oauth2ac.redirect_uri

    @staticmethod
    def validate_bearer_token(token, scopes, request):
        try:
            token = OAuth2ApplicationGrant.objects.get(access_token=token)
        except OAuth2ApplicationGrant.DoesNotExist:
            return False

        all(c.replace("&", " ") in token.characters for c in scopes)

        return True

    @staticmethod
    def validate_client_id(client_id, request, *args, **kwargs):

        try:
            app = Application.objects.get(id=client_id)
        except Application.DoesNotExist:
            return False

        request.client = app
        return True

    @staticmethod
    def validate_code(client_id, code, client, request, *args, **kwargs):
        try:
            ar = AuthorizationCode.objects.get(code=code)
        except AuthorizationCode.DoesNotExist:
            log.warning("Authorization Code {} not found.".format(code))
            return False

        if ar.application != client:
            log.warning("APPLICATION DOESN'T MATCH CLIENT")
            return False

        if ar.application.client_id != client_id:
            log.warning("CLIENT ID DOESN'T MATCH APP ID")
            return False

        request.user = ar.user
        request.scopes = ar.scopes
        request.state = ar.state

        return True

    @staticmethod
    def validate_grant_type(client_id, grant_type, client, request, *args, **kwargs):
        if client.oauth2ac.grant_type and grant_type == client.oauth2ac.grant_type:
            return True

        return False

    @staticmethod
    def validate_redirect_uri(client_id, redirect_uri, request, *args, **kwargs):
        if request.client.oauth2ac.redirect_uri == redirect_uri:
            return True
        return False

    @staticmethod
    def validate_refresh_token(refresh_token, client, request, *args, **kwargs):
        try:
            grant = OAuth2ApplicationGrant.objects.get(refresh_token=refresh_token, application=client)
        except OAuth2ApplicationGrant.DoesNotExist:
            return False

        return all(c.replace("&", " ") in grant.characters for c in request.scopes)

    @staticmethod
    def validate_response_type(client_id, response_type, client, request, *args, **kwargs):
        if response_type == "code":
            return True

    @staticmethod
    def validate_scopes(client_id, scopes, client, request, *args, **kwargs):
        return True

    @staticmethod
    def validate_user(username, password, client, request, *args, **kwargs):
        raise NotImplementedError()


class OAuth2AuthorizationCode(AuthorizationMethod):
    name = "OAuth2 Authorization Code"

    short = "oauth2ac"

    # OAuthlib authorization endpoint
    _authorization_endpoint = WebApplicationServer(OAuthValidator)

    additional_methods = ['access_token']

    @classmethod
    def pre_authorize(cls, user, app, request, *args, **kw):
        uri = request.url
        http_method = request.method
        body = request.body
        headers = request.headers

        try:
            scopes, credentials = cls._authorization_endpoint.validate_authorization_request(
                uri, http_method, body, headers
            )

            session['oauth2_credentials'] = dict(
                client_id=credentials['client_id'],
                redirect_uri=credentials['redirect_uri'],
                state=credentials['state'],
                response_type=credentials['response_type'],
            )
            session.save()

        #TODO: Fix
        except FatalClientError as e:
            return e
        except OAuth2Error as e:
            return e

    @classmethod
    def authorize(cls, user, app, request, characters, all_chars, *args, **kw):
        uri = request.url
        http_method = request.method
        body = request.body
        headers = request.headers

        credentials = {'user': user}
        credentials.update(session['oauth2_credentials'] if 'oauth2_credentials' in session else dict())

        # OAUTH2 specifies that scopes is a string with elements separated by spaces, so we replace character
        # name spaces with an arbitrary character that is not valid in character names.
        scopes = [c.name.replace(" ", "&") for c in (characters)] if not all_chars else ["all_chars"]

        try:
            headers, body, status = cls._authorization_endpoint.create_authorization_response(
                uri, http_method, body, headers, scopes, credentials
            )
            return 'json:', dict(success=True, location=headers['Location'])
        except FatalClientError as e:
            return e

    @classmethod
    def deny_authorize(cls, user, app, request, *args, **kw):
        raise HTTPBadRequest(error="access_denied", error_description="The user declined to authorize your application"
                                                                      " to access their data.")

    @classmethod
    def authenticate(cls, user, app, request, grant, *args, **kw):
        ret = cls.authorize(user, app, request, grant.characters, grant.all_chars, *args, **kw)
        grant.delete()
        return ret[1]['location']

    @classmethod
    def get_application(cls, request, *args, **kw):
        if 'client_id' in kw:
            return Application.objects.get(id=kw['client_id'])
        if 'Authorization' in request.headers:
            # TODO: Temp holdover b/c Bearer tokens in Authorization header
            res = OAuthValidator.verify_http_basic(request)
            if res:
                return res
        if 'token' in kw:
            try:
                token = OAuth2ApplicationGrant.objects.get(access_token=kw['token'])
            except OAuth2ApplicationGrant.DoesNotExist:
                raise HTTPBadRequest()
            return token.application

    @classmethod
    def before_api(cls, *args, **kw):
        from web.core import request
        return cls.get_application(request, *args, **kw)

    @classmethod
    def after_api(cls, response, result, *args, **kw):
        return response

    @classmethod
    def get_token(cls, token, service):
        # TODO: Add support for refresh tokens.
        return OAuth2ApplicationGrant.objects.get(access_token=token, application=service)

    @classmethod
    def access_token(cls, *args, **kwargs):
        from web.core import request
        uri = request.url
        http_method = request.method
        body = request.body
        headers = request.headers

        credentials = dict()

        headers, body, status = cls._authorization_endpoint.create_token_response(
            uri, http_method, body, headers, credentials
        )

        return 'json:', cls.response_from_return(headers, body, status)

    @staticmethod
    def response_from_return(headers, body, status):
        from web.core import response
        response.status_int = status
        response.headers.update(headers)

        # This is a workaround because we use 401 internally to mean redirect to the auth page
        # TODO: We should probably fix this
        if response.status_int == 401:
            response.status_int = 400

        return ast.literal_eval(body)

class AuthenticationRequest(Document):
    meta = dict(
            allow_inheritance = False,
            indexes = [
                    dict(fields=['expires'], expireAfterSeconds=0)
                ]
        )

    application = ReferenceField('Application', db_field='a')
    user = ReferenceField('User', db_field='u')
    grant = ReferenceField('ApplicationGrant', db_field='g')

    success = URLField(db_field='s')
    failure = URLField(db_field='f')

    expires = DateTimeField(db_field='e', default=lambda: datetime.utcnow() + timedelta(minutes=10))

    def __repr__(self):
        return 'AuthenticationRequest({0}, {1}, {2}, {3})'.format(self.id, self.application, self.user, self.grant)


class OAuth2ApplicationGrant(ApplicationGrant):
    access_token = StringField(min_length=25)
    refresh_token = StringField(min_length=25)


class AuthorizationCode(Document):
    meta = dict(
            allow_inheritance = False,
            indexes = [
                    dict(fields=['expires'], expireAfterSeconds=0)
                ]
        )

    application = ReferenceField('Application', db_field='a')
    user = ReferenceField('User', db_field='u')
    code = StringField(db_field='c')
    scopes = ListField(StringField(db_field='s'))
    state = StringField(db_field='t')

    redirect_uri = URLField(db_field='r')

    expires = DateTimeField(db_field='e', default=lambda: datetime.utcnow() + timedelta(minutes=10))

    def __repr__(self):
        return 'AuthorizationCode({0}, {1}, {2}, {3})'.format(self.id, self.application, self.user, self.redirect_uri)
