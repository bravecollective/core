# encoding: utf-8

from web.auth import user
from web.core import Controller, HTTPMethod, request
from web.core.locale import _
from web.core.http import HTTPFound, HTTPNotFound
from marrow.util.bunch import Bunch

from brave.core.character.model import EVECharacter
from brave.core.ban.model import Ban
from brave.core.account.model import User
from brave.core.application.model import Application
from brave.core.util.predicate import authenticate
from brave.core.util import post_only
from brave.core.permission.util import user_has_permission
from brave.core.permission.model import Permission, WildcardPermission, GRANT_WILDCARD


class BanInterface(HTTPMethod):
    
    @authenticate
    def __init__(self, ban):
        super(BanInterface, self).__init__()

        try:
            self.ban = Ban.objects.get(id=ban)
        except Ban.DoesNotExist:
            raise HTTPNotFound()

        if not self.ban.view_perm:
            raise HTTPNotFound()
        
    @authenticate
    def get(self):
        return 'brave.core.ban.template.banDetails', dict(
            ban=self.ban,
            area='ban',
        )

    # Call _current_obj() on user because the mongoengine reference fields don't like the stackedproxy.

    @post_only
    @user_has_permission("{temp}", temp="self.ban.disable_perm")
    def disable(self):
        return 'json:', dict(success=self.ban.disable(user._current_obj()))

    @post_only
    @user_has_permission("{temp}", temp="self.ban.enable_perm")
    def enable(self):
        return 'json:', dict(success=self.ban.enable(user._current_obj()))

    @post_only
    @user_has_permission("{temp}", temp="self.ban.comment_perm")
    def comment(self, comment):
        return 'json:', dict(success=self.ban.comment(user._current_obj(), comment))

    @post_only
    @user_has_permission("{temp}", temp="self.ban.lock_perm")
    def lock(self):
        return 'json:', dict(success=self.ban.lock(user._current_obj()))

    @post_only
    @user_has_permission("{temp}", temp="self.ban.unlock_perm")
    def unlock(self):
        return 'json:', dict(success=self.ban.unlock(user._current_obj()))

    @post_only
    @user_has_permission("{temp}", temp="self.ban.modify_reason_perm")
    def modify_reason(self, reason):
        return 'json:', dict(success=self.ban.modify_reason(user._current_obj(), reason))

    @post_only
    @user_has_permission("{temp}", temp="self.ban.modify_secret_reason_perm")
    def modify_secret_reason(self, reason):
        return 'json:', dict(success=self.ban.modify_secret_reason(user._current_obj(), reason))

    @post_only
    @user_has_permission("{temp}", temp="self.ban.disable_perm")
    def modify_type(self, type, app=None, subarea=None):
        print type
        if type == "app" and app:
            if not user.has_permission(Ban.CREATE_APP_PERM.format(app_short=app)):
                return 'json:', dict(success=False, message="You're not allowed to do this.")
        elif type == "subapp" and subarea:
            if not user.has_permission(Ban.CREATE_SUBAPP_PERM.format(app_short=app, subapp_id=subarea)):
                return 'json:', dict(success=False, message="You're not allowed to do this.")

        return 'json:', dict(success=self.ban.modify_type(user._current_obj(), type, app, subarea))


class BanSearch(HTTPMethod):
    @authenticate
    def get(self, character=None, ip=None, submit=None):

        if not character and not ip:

            return 'brave.core.ban.template.index', dict(
                    area='bans',
                )

        if character:
            temp = character
            character = EVECharacter.objects(name__istartswith=character).first()

            if not character:
                return 'brave.core.ban.template.index', dict(
                    success = False,
                    search_param = temp,
                    area='bans',
                )

            return 'brave.core.ban.template.index', dict(
                    success = True,
                    search_param = temp,
                    results=character.owner.person.bans,
                    area='bans',
                )
        if ip:
            temp = ip
            ip = User.objects(host=ip).first()

            if not ip:
                return 'brave.core.ban.template.index', dict(
                    success = False,
                    search_param = temp,
                    area='bans',
                )

            return 'brave.core.ban.template.index', dict(
                    success = True,
                    search_param = temp,
                    results=ip.person.bans,
                    area='bans',
                )


class BanController(Controller):
    """Entry point for the KEY management RESTful interface."""

    index = BanSearch()

    def __lookup__(self, ban, *args, **kw):
        request.path_info_pop()  # We consume a single path element.
        return BanInterface(ban), args
