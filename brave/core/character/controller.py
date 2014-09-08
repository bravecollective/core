# encoding: utf-8

from web.auth import user
from web.core import Controller, HTTPMethod, request
from web.core.locale import _
from web.core.http import HTTPFound, HTTPNotFound
from marrow.util.bunch import Bunch

from brave.core.character.model import EVECharacter
from brave.core.util.predicate import authenticate
from brave.core.util import post_only
from brave.core.permission.util import user_has_permission
from brave.core.permission.model import Permission, WildcardPermission, GRANT_WILDCARD


class CharacterInterface(HTTPMethod):
    
    @authenticate
    def __init__(self, char):
        super(CharacterInterface, self).__init__()

        try:
            self.char = EVECharacter.objects.get(id=char)
        except EVECharacter.DoesNotExist:
            raise HTTPNotFound()

        if (not self.char.owner or self.char.owner.id != user.id) and not user.has_permission(self.char.view_perm):
            raise HTTPNotFound()

    @authenticate
    def put(self):
        if not self.char.owner or self.char.owner.id != user.id:
            raise HTTPNotFound()
        
        u = user._current_obj()
        u.primary = self.char
        u.save()

        if request.is_xhr:
            return 'json:', dict(success=True)

        raise HTTPFound(location='/character/')
        
    @authenticate
    def get(self):
        if (not self.char.owner or self.char.owner.id != user.id) and not user.has_permission(self.char.view_perm):
            raise HTTPNotFound()
        
        return 'brave.core.character.template.charDetails', dict(
            char=self.char,
            area='admin' if user.admin else 'chars',
            can_grant_some_permission=any(p.id.startswith('core.permission.grant')
                                          for p in user.permissions),
        )
    
    @post_only
    @user_has_permission(Permission.GRANT_PERM, permission_id='permission')
    def add_perm(self, permission=None):
        p = Permission.objects(id=permission)
        if len(p):
            p = p.first()
        else:
            if GRANT_WILDCARD in permission:
                p = WildcardPermission(permission)
            else:
                p = Permission(permission)
            p.save()
        self.char.personal_permissions.append(p)
        self.char.save()
    
    @post_only
    @user_has_permission(Permission.REVOKE_PERM, permission_id='permission')
    def delete_perm(self, permission=None):
        p = Permission.objects(id=permission).first()
        self.char.personal_permissions.remove(p)
        self.char.save()


class CharacterList(HTTPMethod):
    @authenticate
    def get(self, admin=False):
        if admin and not user.has_permission(EVECharacter.LIST_PERM):
            raise HTTPNotFound()
            
        characters = user.characters
        if admin:
            characters = EVECharacter.objects()

        return 'brave.core.character.template.list', dict(
                area='chars',
                admin=bool(admin),
                records=characters
            )


class CharacterController(Controller):
    """Entry point for the KEY management RESTful interface."""

    index = CharacterList()

    def __lookup__(self, char, *args, **kw):
        request.path_info_pop()  # We consume a single path element.
        return CharacterInterface(char), args
