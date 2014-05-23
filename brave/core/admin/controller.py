# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime

from web.auth import user
from web.core import Controller, HTTPMethod, request
from web.core.locale import _
from web.core.http import HTTPFound, HTTPNotFound

from brave.core.character.model import EVECharacter, EVECorporation, EVEAlliance
from brave.core.group.model import Group
from brave.core.group.acl import ACLList
from brave.core.util.predicate import authorize, is_administrator
from brave.core.key.model import EVECredential
from brave.core.account.model import User

class AdminInterface(HTTPMethod):
    
    @authorize(is_administrator)
    def get(self):
        return 'brave.core.admin.template.search', dict(
            )

class AdminController(Controller):
    """Entry point for the Search RESTful interface."""

    #index = AdminInterface()

    def index(self):
        return 'brave.core.admin.template.search', dict(area='admin')
    
    def search(self, Character=None, charMethod=None, Alliance=None, Corporation=None, group=None, KeyID=None,
                KeyMask=None, Username=None, userMethod=None, IP=None):
        """Handles the /admin/search page, which is the post result of /admin/."""
        
        # Have to be an admin to access admin pages.            
        if not is_administrator:
            raise HTTPNotFound()
        
        # Seed the initial results with all of the respective objects.
        chars = EVECharacter.objects()
        keys = EVECredential.objects()
        users = User.objects()
            
        # Go through and check all of the possible posted values
        
        # Limit chars to the character name entered.
        if Character:
            if charMethod == 'contains':
                chars = chars.filter(name__icontains=Character)
            elif charMethod == 'starts':
                chars = chars.filter(name__istartswith=Character)
            elif charMethod == 'is':
                chars = chars.filter(name__iexact=Character)
            else:
                return 'json:', dict(success=False, message=_("You broke the web page. Good Job."))
        
        # Limit to characters in the specified alliance.
        if Alliance:
            Alliance = EVEAlliance.objects(name=Alliance).first()
            chars = chars.filter(alliance=Alliance)
        
        # Limit to characters in the specified corporation.
        if Corporation:
            Corporation = EVECorporation.objects(name=Corporation).first()
            chars = chars.filter(corporation=Corporation)
        
        # Limit to characters in the specified group.
        if group:
            groupList = []
            for c in chars:
                if group in c.tags:
                    groupList.append(c.id)
                    
            chars = chars.filter(id__in=groupList)
        
        # Limit to keys with the specified ID.
        if KeyID:
            keys = keys.filter(key=KeyID)
        
        # Limit to keys with the specified Mask.
        if KeyMask:
            keys = keys.filter(_mask=KeyMask)
        
        # Limit to users with the specified username.
        if Username:
            if userMethod == 'contains':
                users = users.filter(username__icontains=Username)
            elif userMethod == 'starts':
                users = users.filter(username__istartswith=Username)
            elif userMethod == 'is':
                users = users.filter(username__iexact=Username)
            else:
                return 'json:', dict(success=False, message=_("You broke the web page. Good Job."))
        
        # Limit to users with the specified IP address.
        if IP:
            users = users.filter(host=IP)

        # Only one search row is returned.
        # Choose to return characters > keys > users.
        if Character or Alliance or Corporation or group:
            kind = 'Character'
            results = chars
        elif KeyID or KeyMask or KeyMask == 0:
            kind = 'Key'
            results = keys
        elif Username or IP:
            kind = 'User'
            results = users
        else:
            return 'json:', dict(success=False, message=_("You broke the web page. Good Job."))

        result = []
        for obj in results:
            result.append(obj)

        return 'brave.core.admin.template.search', dict(success=True, kind=kind, result=result)
    
    def __lookup__(self, key, *args, **kw):
        request.path_info_pop()  # We consume a single path element.
        return AdminInterface(key), args
