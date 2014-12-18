# encoding: utf-8

from __future__ import unicode_literals

from operator import __or__

from web.core import request, response, url, config
from web.core.http import HTTPUnauthorized
from web.auth import user
from mongoengine import Q
from marrow.util.url import URL
from marrow.util.object import load_object as load
from marrow.util.convert import boolean

from brave.core.api.model import AuthenticationBlacklist, AuthenticationRequest
from brave.core.api.util import SignedController, get_token
from brave.core.util.eve import EVECharacterKeyMask, api
from brave.core.permission.model import create_permission


log = __import__('logging').getLogger(__name__)


class PermissionAPI(SignedController):
    def register(self, permission, description):
        """Allows applications to register new permissions that they use. This is intended so that applications can
        have permissions they won't necessarily know about before intialization (run-time permissions), such as
        the ability to write to a specific forum. Applications are restricted to registering applications within their
        own scope (as enforced elsewhere in the permissions setup).
        
        permission: The permission id that the application wishes to register
        description: The description for the permission being registered.
        
        returns:
            status: Success of the call
            code: Error code if the call fails
            message: Verbose description of the issue, should not be used to identify issue.
        """
        
        app = request.service
        
        if not permission.startswith(app.short + "."):
            log.debug('{0} attempted to register {1} but was unable to due to having an incorrect short.'.format(
                app.name,
                permission))
                
            return dict(
                status="error",
                code="argument.permission.invalid",
                message="The permission supplied does not start with the short allocated to your application."
            )
        
        # create_permission returns False if there's an id conflict
        if not create_permission(permission, description):
            log.debug('{0} attempted to register {1} but was unable to due to {1} already existing.'.format(
                app.name,
                permission))
                
            return dict(
                status="error",
                code="argument.permission.conflict",
                message="The permission supplied already exists."
            )
        
        log.info('{0} successfully registered {1}.'.format(app.name, permission))
        return dict(status="success")


class CoreAPI(SignedController):
    permission = PermissionAPI()
    

    
    def deauthorize(self, token):
        from brave.core.application.model import ApplicationGrant
        count = ApplicationGrant.objects(id=token, application=request.service).delete()
        return dict(success=bool(count))
    
    def reauthorize(self, token, success=None, failure=None):
        result = self.deauthorize(token)
        if not result['success']: return result
        return self.authorize(success=success, failure=failure)
    
    def info(self, token):
        from brave.core.group.model import Group

        # Step 1: Get the appropriate grant.
        token = get_token(request, token)

        # Step 2: Assemble the information for each character
        def char_info(char):
            # Ensure that this character still belongs to this user. 
            if char.owner != token.user:
                token.remove_character(char)
                token.reload()
                return None

            # Match ACLs.
            tags = []
            for group in Group.objects(id__in=request.service.groups):
                if group.evaluate(token.user, char):
                    tags.append(group.id)

            return dict(
                character = dict(id=char.identifier, name=char.name),
                corporation = dict(id=char.corporation.identifier, name=char.corporation.name),
                alliance = (dict(id=char.alliance.identifier, name=char.alliance.name)
                            if char.alliance
                            else None),
                tags = tags,
                perms = char.permissions_tags(token.application),
                expires = None,
                mask = token.mask,
            )

        characters_info = filter(None, map(char_info, token.characters))
        if not characters_info:
            raise HTTPUnauthorized()

        info = char_info(token.default_character)
        info['characters'] = characters_info
        return info

    def authorize(self, success=None, failure=None):

        from brave.core.api.auth.controller import AuthorizeController

        return AuthorizeController.core.auth_method.api_authorize(success, failure)
