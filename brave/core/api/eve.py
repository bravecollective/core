# encoding: utf-8

from __future__ import unicode_literals

from operator import __or__

from web.core import request, response, url, config
from web.auth import user
from mongoengine import Q
from marrow.util.url import URL
from marrow.util.object import load_object as load
from marrow.util.convert import boolean

from brave.core.application.model import Application
from brave.core.api.model import AuthenticationBlacklist, AuthenticationRequest
from brave.core.api.util import SignedController
from brave.core.util.eve import api
from brave.core.character.model import EVECharacter

log = __import__('logging').getLogger(__name__)


class ProxyAPI(SignedController):
    def __default__(self, group, endpoint, token=None, anonymous=None, **kw):
        from brave.core.application.model import ApplicationGrant

        anonymous = None if anonymous is None else boolean(anonymous)

        log.info(
            "service={0!r} group={1} endpoint={2} token={3} anonymous={4} data={5}".format(
                request.service, group, endpoint, token, anonymous, kw
            ))

        # Prevent access to certain overly-broad API calls.
        if group == 'account' and endpoint != 'AccountStatus':
            return dict(success=False, reason='endpoint.restricted',
                        message="Access restricted to endpoint: {0}.{1}".format(
                            group, endpoint))

        try:  # Get the appropriate grant.
            token = ApplicationGrant.objects.get(id=token,
                                                 application=request.service) if token else None
        except ApplicationGrant.DoesNotExist:
            return dict(success=False, reason='grant.invalid',
                        message="Application grant invalid or expired.")

        if token and token.user.person.banned(app=token.application.short):
            return dict(
                success=False,
                message="This user has been banned from accessing this application."
            )

        try:  # Load the API endpoint.
            call = getattr(getattr(api, group, None), endpoint)
        except AttributeError:
            return dict(success=False, reason='endpoint.invalid',
                        message="Unknown API endpoint: {0}.{1}".format(
                            group, endpoint))

        key = None
        if anonymous is False or token or call.mask:
            # Check that this grant allows calls to this API endpoint.
            if call.mask and (
                            not token or not token.mask or not token.mask.has_access(
                        call.mask)):
                return dict(success=False, reason='grant.unauthorized',
                            message="Not authorized to call endpoint: {0}.{1}".format(
                                group, endpoint))

            if call.name.startswith('char'):
                try:
                    character = EVECharacter.objects.get(
                        identifier=kw['characterID'])
                except KeyError:
                    if len(token.characters) == 1:
                        character = token.characters[0]
                    else:
                        return dict(success=False,
                                    reason='character.notspecified',
                                    message="Must pass a characterID parameter")
                except EVECharacter.DoesNotExist:
                    return dict(success=False, reason='character.notfound',
                                message="Could not find a character with that identifier")
                # Find an appropriate key to use for this request if one is required or anonymous=False.
                key = character.credential_for(call.mask)
                if not key:
                    return dict(success=False, reason='key.notfound',
                                message="Could not find EVE API key that authorizes endpoint: {0}.{1}".format(
                                    group, endpoint))

        try:  # Perform the query or get the cached result.
            result = call(key, **kw) if key else call(**kw)
        except Exception as e:
            log.exception("Unable to process request.")
            return dict(success=False, reason='eve.unknown',
                        message="Encountered unexpected error during EVE API call.",
                        detail=unicode(e))

        # Ensure the presence of a 'success' key for quick validation of calls and return the result.
        result.update(success=True)
        return result
