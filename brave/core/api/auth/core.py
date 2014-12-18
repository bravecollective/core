from brave.core.api.auth.model import AuthorizationMethod
from brave.core.application.model import Application, ApplicationGrant
from brave.core.api.util import parse_http_basic
from brave.core.character.model import EVECharacter
from brave.api.controller import SignedController
from brave.core.api.model import AuthenticationBlacklist, AuthenticationRequest

from datetime import datetime, timedelta
from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, StringField, EmailField, URLField, DateTimeField, BooleanField, ReferenceField, ListField, IntField
from oauthlib.oauth2 import RequestValidator
from web.core.http import HTTPBadRequest
from web.core import session, response, request, config, url
from marrow.util.url import URL
from mongoengine import Q
from operator import __or__
from marrow.util.convert import boolean


log = __import__('logging').getLogger(__name__)


class CoreLegacy(AuthorizationMethod):
    name = "BRAVE Core Legacy Auth"

    short = "core_legacy"

    additional_methods = ['api_authorize', 'auth']

    @classmethod
    def pre_authorize(cls, user, app, request, *args, **kw):
        return

    @classmethod
    def authorize(cls, user, app, request, characters, all_chars, *args, **kw):
        ar = cls._ar(kw.get('ar'))

        mask = ar.application.mask.required
        grant = ApplicationGrant(user=user, application=ar.application, _mask=mask, expires=datetime.utcnow() + timedelta(days=ar.application.expireGrantDays), chars=characters if characters else user.characters, all_chars=all_chars)
        grant.save()

        ar.user = user
        ar.grant = grant
        ar.expires = datetime.utcnow() + timedelta(minutes=10)  # extend to allow time for verification
        ar.save()

        target = URL(ar.success)
        target.query.update(dict(token=str(grant.id)))
        return 'json:', dict(success=True, location=str(target))

    @classmethod
    def deny_authorize(cls, user, app, request, *args, **kw):
        # Deny access.
        ar = cls._ar(kw.get('ar'))

        ar.user = user
        ar.grant = None
        ar.expires = datetime.utcnow() + timedelta(minutes=10)  # extend to allow time for verification
        ar.save()

        target = URL(ar.failure)
        target.query.update(dict(token=str(ar.id)))

        return 'json:', dict(success=True, location=str(target))

    @classmethod
    def authenticate(cls, user, app, request, grant, *args, **kw):
        ar = cls._ar(kw.get('ar'))
        ngrant = ApplicationGrant(user=user, application=ar.application, _mask=grant._mask, expires=grant.expires, chars=grant.characters, all_chars=grant.all_chars)
        ngrant.save()

        ar.user = user
        ar.grant = ngrant
        ar.expires = datetime.utcnow() + timedelta(minutes=10)  # extend to allow time for verification
        ar.save()

        r = grant.delete()

        target = URL(ar.success)
        target.query.update(dict(token=str(ngrant.id)))
        return str(target)

    @classmethod
    def get_application(cls, request, *args, **kw):
        return cls._ar(kw['ar']).application

    @classmethod
    def _ar(cls, ar):
        return AuthenticationRequest.objects.get(id=ar)

    @staticmethod
    def api_authorize(success=None, failure=None):
        """Prepare a incoming session request.

        Error 'message' attributes are temporary; base your logic on the status and code attributes.

        success: web.core.url:URL (required)
        failure: web.core.url:URL (required)

        returns:
            location: web.core.url:URL
                the location to direct users to
        """

        # Ensure success and failure URLs are present.

        if success is None:
            response.status_int = 400
            return dict(
                    status = 'error',
                    code = 'argument.success.missing',
                    message = "URL to return users to upon successful authentication is missing from your request."
                )

        if failure is None:
            response.status_int = 400
            return dict(
                    status = 'error',
                    code = 'argument.failure.missing',
                    message = "URL to return users to upon authentication failure or dismissal is missing from your request."
                )

        # Also ensure they are valid URIs.

        try:
            success_ = success
            success = URL(success)
        except:
            response.status_int = 400
            return dict(
                    status = 'error',
                    code = 'argument.success.malformed',
                    message = "Successful authentication URL is malformed."
                )

        try:
            failure_ = failure
            failure = URL(failure)
        except:
            response.status_int = 400
            return dict(
                    status = 'error',
                    code = 'argument.response.malformed',
                    message = "URL to return users to upon successful authentication is missing from your request."
                )

        # Deny localhost/127.0.0.1 loopbacks and 192.* and 10.* unless in development mode.

        if not boolean(config.get('debug', False)) and (success.host in ('localhost', '127.0.0.1') or \
                success.host.startswith('192.168.') or \
                success.host.startswith('10.')):
            response.status_int = 400
            return dict(
                    status = 'error',
                    code = 'development-only',
                    message = "Loopback and local area-network URLs disallowd in production."
                )

        # Check blacklist and bail early.

        if AuthenticationBlacklist.objects(reduce(__or__, [
                    Q(scheme=success.scheme), Q(scheme=failure.scheme),
                    Q(protocol=success.port or success.scheme), Q(protocol=failure.port or failure.scheme),
                ] + ([] if not success.host else [
                    Q(domain=success.host)
                ]) + ([] if not failure.host else [
                    Q(domain=failure.host)
                ]))).count():
            response.status_int = 400
            return dict(
                    status = 'error',
                    code = 'blacklist',
                    message = "You have been blacklisted.  To dispute, contact {0}".format(config['mail.blackmail.author'])
                )

        # TODO: Check DNS.  Yes, really.

        # Generate authentication token.

        log.info("Creating request for {0} with callbacks {1} and {2}.".format(request.service, success_, failure_))
        ar = AuthenticationRequest(
                request.service,  # We have an authenticated request, so we know the service ID is valid.
                success = success_,
                failure = failure_
            )
        ar.save()

        return dict(
                location = url.complete('/api/auth/core/auth/{0}'.format(ar.id))
            )


    @staticmethod
    def auth(ar=None, *args, **kw):
        """This is used because we can't redirect with arguments to the normal /authorize endpoint because the
        authentication check will strip any provided get arguments, and adding the argument to the URL as part of the
        path will get it detected as an additional_method and thus rejected. Alternatively, we could change from using
        the root of the Auth path as the authentication endpoint for all AuthorizationMethods, but this way was more
        convenient."""

        from brave.core.api.auth.controller import AuthorizeController

        return AuthorizeController.core.index(ar=ar, *args, **kw)
