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
        print "YOLO2"
        return 'brave.core.admin.template.search', dict(
            )

class AdminController(Controller):
    """Entry point for the Search RESTful interface."""

    print "YOLO1"

    #index = AdminInterface()

    def index(self):
        return 'brave.core.admin.template.search', dict(area='admin')
    
    print "YOLO3"
    
    def search(self, Character=None, charMethod=None, Alliance=None, Corporation=None, KeyID=None, KeyMask=None,
                Username=None, userMethod=None, IP=None):
                    
        if not is_administrator:
            raise HTTPNotFound()
                    
        chars = EVECharacter.objects()
        keys = EVECredential.objects()
        users = User.objects()
            
        """    if Character:
            if charMethod == 'contains':
                chars = chars.filter(name__icontains=Character)
                
                keyList = []
                for k in EVECredential.objects:
                    for c in k.characters:
                        if Character.lower() in c.name.lower():
                            keyList.append(k.id)
                keys = keys.filter(id__in=keyList)
                
                userList = []
                for l in User.objects:
                    for c in l.characters:
                        if Character.lower() in c.name.lower():
                            userList.append(l.id)
                users = users.filter(id__in=userList)
            elif charMethod == 'starts':
                chars = chars.filter(name__istartswith=Character)
                
                keyList = []
                for k in EVECredential.objects:
                    for c in k.characters:
                        if Character.lower() in c.name.lower()[:len(Character)]:
                            keyList.append(k.id)
                keys = keys.filter(id__in=keyList)
                
                userList = []
                for l in User.objects:
                    for c in l.characters:
                        if Character.lower() in c.name.lower()[:len(Character)]:
                            userList.append(l.id)
                users = users.filter(id__in=userList)
            elif charMethod == 'is':
                chars = chars.filter(name__iexact=Character)
                
                keyList = []
                for k in EVECredential.objects:
                    for c in k.characters:
                        if Character.lower() == c.name.lower():
                            keyList.append(k.id)
                keys = keys.filter(id__in=keyList)
                
                userList = []
                for l in User.objects:
                    for c in l.characters:
                        if Character.lower() == c.name.lower():
                            userList.append(l.id)
                users = users.filter(id__in=userList)
            else:
                return 'json:', dict(success=False, message=_("You broke the web page. Good Job."))
                
        if Alliance:
            chars = chars.filter(alliance.name__iexact=Alliance)
            keys = keys.filter("""
            
        if Character:
            if charMethod == 'contains':
                chars = chars.filter(name__icontains=Character)
            elif charMethod == 'starts':
                chars = chars.filter(name__istartswith=Character)
            elif charMethod == 'is':
                chars = chars.filter(name__iexact=Character)
            else:
                return 'json:', dict(success=False, message=_("You broke the web page. Good Job."))
                
        if Alliance:
            Alliance = EVEAlliance.objects(name=Alliance).first()
            chars = chars.filter(alliance=Alliance)
            
        if Corporation:
            Corporation = EVECorporation.objects(name=Corporation).first()
            chars = chars.filter(corporation=Corporation)
            
        if KeyID:
            keys = keys.filter(key=KeyID)
            
        if KeyMask:
            keys = keys.filter(_mask=KeyMask)
            
        if Username:
            if userMethod == 'contains':
                users = users.filter(username__icontains=Username)
            elif userMethod == 'starts':
                users = users.filter(username__istartswith=Username)
            elif userMethod == 'is':
                users = users.filter(username__iexact=Username)
            else:
                return 'json:', dict(success=False, message=_("You broke the web page. Good Job."))
                
        if IP:
            users = users.filter(host=IP)

        if Character or Alliance or Corporation:
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
        
    print "YOLO4"
    
    def __lookup__(self, key, *args, **kw):
        request.path_info_pop()  # We consume a single path element.
        return AdminInterface(key), args
