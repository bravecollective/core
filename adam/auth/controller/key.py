# encoding: utf-8

from web.auth import user
from web.core import Controller, HTTPMethod, request, config
from web.core.locale import _
from web.core.http import HTTPUnauthorized

from adam.auth.model.eve import EVECredential
from adam.auth.util.predicate import authorize, authenticated, is_administrator




class KeyController(Controller):
    """Entry point for the KEY management RESTful interface."""
    
    @authorize(authenticated)
    def __before__(self, *args, **kw):
        """Secure all methods."""
        return args, kw
    
    def index(self, admin=False):
        if admin and not user.admin:
            raise HTTPUnauthorized("Must be administrative user.")
        
        return "adam.auth.template.key.list", dict(
                area = 'keys',
                admin = bool(admin),
                records = user.credentials
            )
