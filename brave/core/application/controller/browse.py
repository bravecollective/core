# encoding: utf-8

from __future__ import unicode_literals

from web.auth import user
from web.core import Controller, HTTPMethod, request
from web.core.locale import _
from web.core.http import HTTPFound, HTTPNotFound

from brave.core.application.model import Application
from brave.core.util.predicate import authorize, authenticate
from brave.core.permission.model import Permission


log = __import__('logging').getLogger(__name__)



class ApplicationAuthorization(HTTPMethod):
    def __init__(self, app):
        self.app = app
    
    def get(self):
        # TODO: Return the authorization form.
        # Make sure to have a timestamped OTP generated for this session required for the post.
        return ""
    
    def post(self, **kw):
        # TODO: Process the authorization request.
        return ""


class ApplicationInterface(Controller):
    def __init__(self, app):
        super(ApplicationInterface, self).__init__()
        
        try:
            self.app = Application.objects.get(id=app)
        except Application.DoesNotExist:
            raise HTTPNotFound()
        
        self.authorize = ApplicationAuthorization(self.app)
    
    def index(self):
        # TODO: Show a description and other details of the application.
        return ""


class BrowseController(Controller):
    @authenticate
    def index(self):
        records = list()
        devRecords = list()
        
        # Cache the user's permissions
        user_perms = user.permissions
        
        # Retrieve non-development applications that the user is able to authorize
        for r in Application.objects(development__in=[False, None]):
            if Permission.set_grants_permission(user_perms, r.authorize_perm):
                records.append(r)
        
        # Retrieve development applications that the user is able to authorize
        for r in Application.objects(development=True):
            if Permission.set_grants_permission(user_perms, r.authorize_perm):
                devRecords.append(r)
        
        return 'brave.core.application.template.list_apps', dict(
                area = 'apps',
                records = records,
                devRecords = devRecords
            )
    
    def __lookup__(self, app, *args, **kw):
        request.path_info_pop()  # We consume a single path element.
        return ApplicationInterface(app), args
