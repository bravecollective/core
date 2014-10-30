# encoding: utf-8

from __future__ import unicode_literals

from web.auth import user
from web.core import Controller, HTTPMethod, request
from web.core.locale import _
from web.core.http import HTTPFound, HTTPNotFound

from brave.core.application.controller.browse import BrowseController
from brave.core.application.controller.manage import ManagementController
from brave.core.application.model import ApplicationGrant
from brave.core.application.form import edit_grant
from brave.core.character.model import EVECharacter
from brave.core.util.predicate import authorize, authenticate


log = __import__('logging').getLogger(__name__)


class GrantInterface(HTTPMethod):
    def __init__(self, grant):
        super(GrantInterface, self).__init__()
        
        try:
            self.grant = ApplicationGrant.objects.get(id=grant)
        except ApplicationGrant.DoesNotExist:
            raise HTTPNotFound()

        if self.grant.user.id != user.id:
            raise HTTPNotFound()

    @authenticate
    def get(self):
        if not request.is_xhr:
            raise HTTPNotFound()

        grant = self.grant
        user = grant.user
        
        data = {str(c.identifier):(c in grant.characters) for c in user.characters}
        data['all'] = grant.all_chars
        
        return 'brave.core.template.form', dict(
                kind = _('Application Grant'),
                form = edit_grant(grant),
                data = data,
            )

    @authenticate
    def post(self, **kwargs):
        if not request.is_xhr:
            raise HTTPNotFound()

        grant = self.grant
        valid, invalid = edit_grant(grant).native(kwargs)

        new_characters = []
        for key, value in valid.items():

            if key == 'all':
                if not value and grant.application.require_all_chars:
                    continue
                grant.all_chars = value
                continue
            
            if not value:
                continue
            
            try:
                character = EVECharacter.objects.get(identifier=int(key))
            except EVECharacter.DoesNotExist:
                continue

            # Make sure the character is owned by the grant owner.
            if character.owner != self.grant.user:
                continue

            new_characters.append(character)

        if new_characters:
            grant.chars = new_characters
            grant.save()
        elif grant.all_chars:
            grant.chars = user.characters
            grant.save()
        else:
            grant.delete()

        return 'json:', {'success': True}

    @authenticate
    def delete(self):
        log.info("REVOKE %r %r", self.grant.user, self.grant.application)
        
        try:
            self.grant.delete()
        except:
            log.exception("Error revoking grant.")
            return 'json:', dict(
                    success = False,
                    message = _("Unable to revoke application permission.")
                )

        if request.is_xhr:
            return 'json:', dict(
                    success = True,
                    message = _("Successfully revoked application permissions.")
                )

        raise HTTPFound(location='/application/')


class GrantList(HTTPMethod):
    @authenticate
    def get(self):
        records = ApplicationGrant.objects(
                user = user._current_obj()
            ).order_by('-id')
        
        return 'brave.core.application.template.list_grants', dict(
                area = 'apps',
                records = records
            )


class GrantController(Controller):
    index = GrantList()
    
    browse = BrowseController()
    manage = ManagementController()
    
    def __lookup__(self, grant, *args, **kw):
        request.path_info_pop()  # We consume a single path element.
        return GrantInterface(grant), args
