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
from brave.core.api.model import AuthenticationBlacklist, AuthenticationRequest, Ban
from brave.core.api.util import SignedController
from brave.core.util.eve import EVECharacterKeyMask


log = __import__('logging').getLogger(__name__)


class CoreAPI(SignedController):
    def authorize(self, success=None, failure=None):
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
                location = url.complete('/authorize/{0}'.format(ar.id))
            )
    
    def deauthorize(self, token):
        from brave.core.application.model import ApplicationGrant
        count = ApplicationGrant.objects(id=token, application=request.service).delete()
        return dict(success=bool(count))
    
    def reauthorize(self, token, success=None, failure=None):
        result = self.deauthorize(token)
        if not result['success']: return result
        return self.authorize(success=success, failure=failure)
    
    def info(self, token):
        from brave.core.application.model import ApplicationGrant
        from brave.core.group.model import Group
        
        # Step 1: Get the appropraite grant.
        token = ApplicationGrant.objects.get(id=token, application=request.service)
        character = token.character
        
        # Step 2: Check if the character has been banned.
        if character.banned:
            return dict(
                success = False,
                reason = 'char.banned'
            )
        
        # Step 3: Update info about the character from the EVE API
        mask, key = character.credential_multi_for((EVECharacterKeyMask.CHARACTER_SHEET,
         EVECharacterKeyMask.CHARACTER_INFO_PUBLIC, EVECharacterKeyMask.NULL))
        
        # User has no keys registered.
        if not key:
            return None
            
        key.pull()
        
        # Step 4: Match ACLs.
        tags = []
        for group in Group.objects(id__in=request.service.groups):
            if group.evaluate(token.user, character):
                tags.append(group.id)
        
        return dict(
                character = dict(id=character.identifier, name=character.name),
                corporation = dict(id=character.corporation.identifier, name=character.corporation.name),
                alliance = dict(id=character.alliance.identifier, name=character.alliance.name) if character.alliance else None,
                tags = tags,
                expires = None,
                mask = token.mask
            )
            
    def blacklist(self, kind=None, lookup=None):
        """Check if lookup of type kind (char or IP) is banned.
        
        Returns all bans that match lookup using a contains filter, unless lookup < 9 characters,
        in which case it will do an exact match (to prevent people from just getting the entire ban list.
        If the queried ban is an IP address, it will return only exact matches. Wildcards are not supported
        for security and privacy reasons."""
        
        # Check that argument kind is supplied.
        if not kind:
            return 'json:', dict(success=False, reason='kind.missing', message='Argument kind is required.')
        
        # Check that the argument kind is a valid choice (char for character lookups and IP for IP lookups).
        if kind != 'char' and kind != 'IP':
            return 'json:', dict(success=False, reason='kind.invalid', message='Argument kind must be "char" or "IP".')
        
        # Verify that the argument lookup was supplied.
        if not lookup:
            return 'json:', dict(success=False, reason='lookup.missing', message='Argument lookup is required.')
        
        # Search for bans that meet the specified characteristics.
        if kind == 'char' and len(lookup) > 8:
            bans = Ban.objects(characters__character__contains=lookup)
        elif kind == 'char':
            bans = Ban.objects(characters__character__iexact=lookup)
        else:
            bans = Ban.objects(IPs__host=lookup)
            
        if not len(bans):
            return 'json:', dict(success=True, bans=None)
        else:
            return 'json:', dict(success=True, bans=bans)
