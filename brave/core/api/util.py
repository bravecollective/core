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
            raise HTTPBadRequest("Authorization method with short {} not found.".format(auth))

        request.auth_method = auth_method
        request.service = auth_method.before_api(*args, **kw)

        if not auth_method.short in request.service.auth_methods:
            raise HTTPBadRequest("This application is not allowed to use this auth_method.")

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


def get_token(request, token):
    if request.service.oauth_redirect_uri:
        return ApplicationGrant.objects.get(oauth_access_token=token, application=request.service)
    else:
        return ApplicationGrant.objects.get(id=token, application=request.service)

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
