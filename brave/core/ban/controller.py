# encoding: utf-8

from web.auth import user
from web.core import Controller, HTTPMethod, request
from web.core.locale import _
from web.core.http import HTTPFound, HTTPNotFound
from marrow.util.bunch import Bunch

from brave.core.character.model import EVECharacter
from brave.core.ban.model import Ban, PersonBan
from brave.core.application.model import Application
from brave.core.util.predicate import authenticate
from brave.core.util import post_only
from brave.core.permission.util import user_has_permission
from datetime import timedelta


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
        if self.ban.locked and not user.has_permission(self.ban.unlock_perm):
            return 'json:', dict(success=False, message="Sorry, this ban is locked, and therefore immutable.")

        return 'json:', dict(success=self.ban.disable(user._current_obj()))

    @post_only
    @user_has_permission("{temp}", temp="self.ban.enable_perm")
    def enable(self):
        if self.ban.locked and not user.has_permission(self.ban.unlock_perm):
            return 'json:', dict(success=False, message="Sorry, this ban is locked, and therefore immutable.")

        return 'json:', dict(success=self.ban.enable(user._current_obj()))

    @post_only
    @user_has_permission("{temp}", temp="self.ban.comment_perm")
    def comment(self, comment):
        if self.ban.locked and not user.has_permission(self.ban.unlock_perm):
            return 'json:', dict(success=False, message="Sorry, this ban is locked, and therefore immutable.")

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
        if self.ban.locked and not user.has_permission(self.ban.unlock_perm):
            return 'json:', dict(success=False, message="Sorry, this ban is locked, and therefore immutable.")

        return 'json:', dict(success=self.ban.modify_reason(user._current_obj(), reason))

    @post_only
    @user_has_permission("{temp}", temp="self.ban.modify_secret_reason_perm")
    def modify_secret_reason(self, reason):
        if self.ban.locked and not user.has_permission(self.ban.unlock_perm):
            return 'json:', dict(success=False, message="Sorry, this ban is locked, and therefore immutable.")

        return 'json:', dict(success=self.ban.modify_secret_reason(user._current_obj(), reason))

    @post_only
    @user_has_permission("{temp}", temp="self.ban.disable_perm")
    def modify_type(self, type, app=None, subarea=None):
        if self.ban.locked and not user.has_permission(self.ban.unlock_perm):
            return 'json:', dict(success=False, message="Sorry, this ban is locked, and therefore immutable.")

        if type == "app" and app:
            if not user.has_permission(Ban.CREATE_APP_PERM.format(app_short=app)):
                return 'json:', dict(success=False, message="You're not allowed to do this.")
        elif type == "subapp" and subarea:
            if not user.has_permission(Ban.CREATE_SUBAPP_PERM.format(app_short=app, subapp_id=subarea)):
                return 'json:', dict(success=False, message="You're not allowed to do this.")

        return 'json:', dict(success=self.ban.modify_type(user._current_obj(), type, app, subarea))


class BanSearch(HTTPMethod):
    @authenticate
    def get(self, character=None, submit=None):

        if not character:

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

            bans = []
            # We only show enabled bans in the search window to users wihtout permission
            for b in character.owner.person.bans:
                if b.enabled:
                    bans.append(b)
                    continue

                if user.has_permission(b.view_perm):
                    bans.append(b)

            return 'brave.core.ban.template.index', dict(
                    success = True,
                    search_param = temp,
                    results=bans,
                    area='bans',
                )

    @authenticate
    def post(self, char, duration, reason, ban_type, secret_reason=None, app=None, subarea=None):
        if ban_type == "global":
            if not user.has_permission(Ban.CREATE_GLOBAL_PERM):
                return 'json:', dict(success=False, message="You don't have permission to do this.")

            app = None
            subarea = None

        elif ban_type == "service":
            if not user.has_permission(Ban.CREATE_SERVICE_PERM):
                return 'json:', dict(success=False, message="You don't have permission to do this.")

            app = None
            subarea = None
        elif ban_type == "app":
            if not app:
                return 'json:', dict(success=False, message="You must supply an application for application bans.")

            app = Application.objects(short=app).first()
            if not app:
                return 'json:', dict(success=False, message="Application not found.")

            if not user.has_permission(Ban.CREATE_APP_PERM.format(app_short=app)):
                return 'json:', dict(success=False, message="You don't have permission to do this.")

            subarea = None
        elif ban_type == "subapp":
            if not app:
                return 'json:', dict(success=False, message="You must supply an application for subapp bans.")

            app = Application.objects(short=app).first()
            if not app:
                return 'json:', dict(success=False, message="Application not found.")

            if not user.has_permission(Ban.CREATE_SUBAPP_PERM.format(app_short=app, subapp_id=subarea)):
                return 'json:', dict(success=False, message="You don't have permission to do this.")
        else:
            return 'json:', dict(success=False, message="How about no.")

        if secret_reason and not user.has_permission(getattr(Ban, "MODIFY_SECRET_REASON_" + ban_type.upper() + "_PERM")):
            return 'json:', dict(success=False, message="No secret reasons for you!")

        char = EVECharacter.objects(name__iexact=char).first()
        if not char:
            return 'json:', dict(success=False, message="Character provided was not found.")

        if not reason:
            return 'json:', dict(success=False, message="You must provide a reason for the ban.")

        # The JS from the client will send empty strings, which mongoengine will interpret as actual values

        if not secret_reason:
            secret_reason = None

        duration = timedelta(hours=int(duration)) if duration != 0 else None

        ban = PersonBan.create(banner=user._current_obj(), duration=duration,
                               ban_type=ban_type, reason=reason, person=char.owner.person, banned_ident=char.name,
                               app=app, subarea=subarea, secret_reason=secret_reason, banned_type="character")
        ban.save()
        return 'json:', dict(success=True, id=str(ban.id))


class BanController(Controller):
    """Entry point for the KEY management RESTful interface."""

    index = BanSearch()
    create = BanSearch()

    def __lookup__(self, ban, *args, **kw):
        request.path_info_pop()  # We consume a single path element.
        return BanInterface(ban), args
