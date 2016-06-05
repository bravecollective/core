# encoding: utf-8

from __future__ import unicode_literals

from web.core import Controller, HTTPMethod
from web.core.locale import _
from web.core.http import HTTPNotFound

from brave.core.character.model import EVECharacter, EVECorporation, \
    EVEAlliance
from brave.core.util.predicate import is_administrator
from brave.core.key.model import EVECredential
from brave.core.account.model import User
from brave.core.permission.util import user_has_permission, \
    user_has_any_permission


class SearchCharInterface(HTTPMethod):
    """Handles /admin/search/char"""

    @user_has_permission('core.admin.search.char')
    def get(self, character=None, charMethod=None, alliance=None,
            corporation=None, group=None, submit=None):

        # Have to be an admin to access admin pages.
        if not is_administrator:
            raise HTTPNotFound()

        if not submit:
            return 'brave.core.admin.template.searchChar', dict(area='admin')

        # Seed the initial results.
        chars = EVECharacter.objects()

        # Go through and check all of the possible posted values

        # Limit chars to the character name entered.
        if character:
            if charMethod == 'contains':
                chars = chars.filter(name__icontains=character)
            elif charMethod == 'starts':
                chars = chars.filter(name__istartswith=character)
            elif charMethod == 'is':
                chars = chars.filter(name__iexact=character)
            else:
                return 'json:', dict(success=False, message=_(
                    "You broke the web page. Good Job."))

        # Limit to characters in the specified alliance.
        if alliance:
            alliance = EVEAlliance.objects(name=alliance).first()
            if alliance is None:
                return 'brave.core.admin.template.searchChar',\
                       dict(area='admin', result=[], success=True)
            else:
                chars = chars.filter(alliance=alliance)

        # Limit to characters in the specified corporation.
        if corporation:
            corporation = EVECorporation.objects(name=corporation).first()
            chars = chars.filter(corporation=corporation)

        # Limit to characters in the specified group.
        if group:
            groupList = []
            for c in chars:
                if group in c.tags:
                    groupList.append(c.id)

            chars = chars.filter(id__in=groupList)

        return 'brave.core.admin.template.searchChar', dict(area='admin',
                                                            result=chars,
                                                            success=True)


class SearchKeyInterface(HTTPMethod):
    """Handles /admin/search/key"""

    @user_has_permission('core.admin.search.key')
    def get(self, keyID=None, keyMask=None, violation=None, submit=None):

        # Have to be an admin to access admin pages.
        if not is_administrator:
            raise HTTPNotFound()

        if not submit:
            return 'brave.core.admin.template.searchKey', dict(area='admin')

        # Seed the initial results.
        keys = EVECredential.objects()

        # Limit to keys with the specified ID.
        if keyID:
            keys = keys.filter(key=keyID)

        # Limit to keys with the specified Mask.
        if keyMask:
            keys = keys.filter(_mask=keyMask)

        # Limit to keys with the specified violation.
        if violation.lower() == "none":
            keys = keys.filter(violation=None)
        elif violation:
            keys = keys.filter(violation__iexact=violation)

        return 'brave.core.admin.template.searchKey', dict(area='admin',
                                                           result=keys,
                                                           success=True)


class SearchUserInterface(HTTPMethod):
    """Handles /admin/search/user"""

    @user_has_permission('core.admin.search.user')
    def get(self, username=None, userMethod=None, ip=None, duplicate=None,
            submit=None):

        # Have to be an admin to access admin pages.
        if not is_administrator:
            raise HTTPNotFound()

        if not submit:
            return 'brave.core.admin.template.searchUser', dict(area='admin')

        # Seed the initial results.
        users = User.objects()

        # Limit to users with the specified username.
        if username:
            if userMethod == 'contains':
                users = users.filter(username__icontains=username)
            elif userMethod == 'starts':
                users = users.filter(username__istartswith=username)
            elif userMethod == 'is':
                users = users.filter(username__iexact=username)
            else:
                return 'json:', dict(success=False, message=_(
                    "You broke the web page. Good Job."))

        # Limit to users with the specified IP address.
        if ip:
            users = users.filter(host=ip)

        # Limit to users with the specified duplicate status
        if duplicate.lower() == "ip":
            users = users.filter(other_accs_IP__exists=True)
        elif duplicate.lower() == "char":
            users = users.filter(other_accs_char_key__exists=True)

        return 'brave.core.admin.template.searchUser', dict(area='admin',
                                                            result=users,
                                                            success=True)


class SearchController(Controller):
    char = SearchCharInterface()
    key = SearchKeyInterface()
    user = SearchUserInterface()


class AdminController(Controller):
    """Entry point for the Search RESTful interface."""

    search = SearchController()

    @user_has_any_permission('core.admin.search.*')
    def index(self):
        return 'brave.core.admin.template.search', dict(area='admin')
