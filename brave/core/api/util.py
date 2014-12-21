# encoding: utf-8

from __future__ import unicode_literals
from web.core import request, response
from web.core.http import HTTPBadRequest
from base64 import b64decode
from webob import Response
from datetime import datetime
from web.core.templating import render

from brave.api.controller import SignedController as OriginalSignedController
from brave.core.application.model import Application, ApplicationGrant
from brave.core.api.auth.controller import AuthorizeController


log = __import__('logging').getLogger(__name__)


class SignedController(OriginalSignedController):
    def __service__(self, identifier):
        return Application.objects.get(id=identifier)

    def __before__(self, *args, **kw):

        auth = kw.get('auth_method', 'core_legacy')
        auth_method = AuthorizeController.get_auth_method(auth)

        if not auth_method:
            return dict(success=False, reason='auth_method.invalid',
                        message="Authorization method with short {} not found.".format(auth))

        request.auth_method = auth_method
        request.service = auth_method.before_api(*args, **kw)

        if not auth_method.short in request.service.auth_methods:
            return dict(success=False, reason='auth_method.not_authorized',
                        message="This application is not allowed to use this auth_method.")

        if 'auth_method' in kw:
            del kw['auth_method']

        return args, kw

    def __after__(self, result, *args, **kw):
        response = Response(status=200, charset='utf-8')
        response.date = datetime.utcnow()
        response.last_modified = result.pop('updated', None)

        ct, body = render('json:', result)
        response.headers[b'Content-Type'] = str(ct)  # protect against lack of conversion in Flup
        response.body = body

        return request.auth_method.after_api(response, result, *args, **kw)


def parse_http_basic(request):
    if not 'Authorization' in request.headers:
        log.debug("No Authorization header found.")
        return False, False

    if len(request.headers['Authorization']) < 6:
        log.debug("Authorization Header too short")
        return False, False

    if not request.headers['Authorization'][:6] == 'Basic ':
        log.debug("Authorization Header incorrect format")
        return False, False

    auth = request.headers['Authorization'][6:]
    auth = b64decode(auth)
    return auth.split(":")


def handle_token(function):
    """Takes the token keyword parameter from the decorated function and replaces it with the ApplicationGrant object
    that it corresponds to. Do not use on API calls where the token can be provided via positional arguments, such as
    where the token is part of the URL."""

    def retrieve_token(self, *args, **kwargs):

        token = None

        if 'token' in kwargs:
            token = kwargs.get('token')
            del kwargs['token']
        elif request.auth_method == 'core_legacy': # Core Legacy Auth does not require a token for all API calls.
            return function(self, *args, **kwargs)

        if not token:
            return dict(success=False, reason='token.missing',
                        message='This authorization method requires a token for all API calls.')

        # Some API calls call others, so the token may already be converted
        if isinstance(token, ApplicationGrant):
            return function(self, *args, **kwargs)

        try:
            token = request.auth_method.get_token(token, request.service)
        except:
            return dict(success=False, reason='grant.invalid', message="Application grant invalid or expired.")

        return function(self, token=token, *args, **kwargs)

    return retrieve_token

def handle_positional_token(function):
    """Takes the token keyword parameter from the decorated function and replaces it with the ApplicationGrant object
    that it corresponds to. Do not use on API calls where the token can be provided via positional arguments, such as
    where the token is part of the URL. If there is no keyword argument called token, we take the first positional
    argument and use that instead. Only for use in API calls where the token is mandatory."""

    def retrieve_token(self, *args, **kwargs):

        if 'token' in kwargs:
            token = kwargs.get('token')
            del kwargs['token']
        elif len(args):
            token = args[0]
            args = args[1:] if len(args) > 1 else ()
        else:
            return dict(success=False, reason='grant.missing', message="Application grant not supplied.")

        # Some API calls call others, so the token may already be converted
        if isinstance(token, ApplicationGrant):
            return function(self, *args, **kwargs)

        try:
            token = request.auth_method.get_token(token, request.service)
        except:
            return dict(success=False, reason='grant.invalid', message="Application grant invalid or expired.")

        return function(self, token=token, *args, **kwargs)

    return retrieve_token

