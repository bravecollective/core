# encoding: utf-8

from __future__ import unicode_literals

from web.auth import user
from web.core import Controller, HTTPMethod, request
from web.core.locale import _
from web.core.http import HTTPFound, HTTPNotFound

from brave.core.application.controller.browse import BrowseController
from brave.core.application.controller.manage import ManagementController
from brave.core.application.model import ApplicationGrant
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
