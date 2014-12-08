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


log = __import__('logging').getLogger(__name__)


class SignedController(OriginalSignedController):
    def __service__(self, identifier):
        return Application.objects.get(id=identifier)

    def __before__(self, *args, **kw):
        if 'X-Service' in request.headers and 'X-Signature' in request.headers:
            # TODO: Better check for if it's an OAUTH or LEGACY app
            if self.__service__(request.headers['X-Service']).oauth_redirect_uri:
                raise HTTPBadRequest()
            super(SignedController, self).__before__(args, kw)
            return args, kw
        """For requests from OAuth clients, we'll accept either an access token or the client credentials as
            verification of identity."""
        # TODO: Handle Bearer tokens in this header
        if 'Authorization' in request.headers:
            id, secret = parse_http_basic(request)
            if id:
                if not self.__service__(id).oauth_redirect_uri:
                    raise HTTPBadRequest()
                request.service = self.__service__(id)
                return args, kw
        if 'client_id' in kw and 'client_secret' in kw:
            if not self.__service__(kw['client_id']).oauth_redirect_uri:
                raise HTTPBadRequest()
            request.service = self.__service__(kw['client_id'])
            return args, kw
        if 'token' in kw:
            try:
                token = ApplicationGrant.objects.get(oauth_access_token=kw['token'])
            except ApplicationGrant.DoesNotExist:
                raise HTTPBadRequest()
            if not token.application.oauth_redirect_uri:
                raise HTTPBadRequest()
            request.service = token.application
            return args, kw

        raise HTTPBadRequest()

    def __after__(self, result, *args, **kw):
        if 'X-Service' in request.headers and 'X-Signature' in request.headers:
            return super(SignedController, self).__after__(result, args, kw)

        response = Response(status=200, charset='utf-8')
        response.date = datetime.utcnow()
        response.last_modified = result.pop('updated', None)

        ct, body = render('json:', result)
        response.headers[b'Content-Type'] = str(ct)  # protect against lack of conversion in Flup
        response.body = body

        return response


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
