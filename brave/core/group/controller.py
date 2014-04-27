# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime

from web.auth import user
from web.core import Controller, HTTPMethod, request
from web.core.locale import _
from web.core.http import HTTPFound, HTTPNotFound

from brave.core.character.model import EVECharacter
from brave.core.group.model import Group
from brave.core.group.acl import ACLList
from brave.core.util.predicate import authorize, is_administrator

log = __import__('logging').getLogger(__name__)

class OneGroupController(HTTPMethod):
    def __init__(self, id):
        super(OneGroupController, self).__init__()

        try:
            self.group = Group.objects.get(id=id)
        except Group.DoesNotExist:
            raise HTTPNotFound()

    @authorize(is_administrator)
    def index(self):
        return 'brave.core.group.template.group', dict(
            area='group',
            group=self.group,
        )

    # Below: the worst ACL editing interface in history.
    # Allows adding or removing characters to the last rule in the list. If the last rule isn't
    # appropriate (a character allow rule) when trying to add a character, we create one, and when
    # trying to remove a character, we just give up.

    @authorize(is_administrator)
    def add_character(self, name=None):
        if not name:
            return 'json:', dict(success=False,
                                 message=_("character name required"))
        q = EVECharacter.objects(name=name)
        assert q.count() <= 1
        if q.count() != 1:
            return 'json:', dict(success=False,
                                 message=_("character not found"))
        c = q.first()

        r = self.group.rules[-1]
        if not (isinstance(r, ACLList) and r.grant and not r.inverse and r.kind == 'c'):
            r = ACLList(grant=True, inverse=False, kind='c', ids=[])
            self.group.rules.append(r)

        if c.identifier in r.ids:
            return 'json:', dict(success=False,
                                 message=_("Character already in rule"))
        r.ids.append(c.identifier)
        success = self.group.save()

        if success:
            return 'json:', dict(success=True)
        return 'json:', dict(success=False,
                             message=_("Failure updating group"))

    @authorize(is_administrator)
    def remove_character(self, name=None):
        if not name:
            return 'json:', dict(success=False,
                                 message=_("character name required"))
        q = EVECharacter.objects(name=name)
        assert q.count() <= 1
        if q.count() != 1:
            return 'json:', dict(success=False,
                                 message=_("character not found"))
        c = q.first()

        r = self.group.rules[-1]
        if not (isinstance(r, ACLList) and r.grant and not r.inverse and r.kind == 'c'):
            return 'json:', dict(success=False,
                                 message=_("Sorry, I don't know what to do!"))
        if not c.identifier in r.ids:
            return 'json:', dict(success=False,
                                 message=_("Character not found in last rule!"))
        r.ids.remove(c.identifier)
        success = self.group.save()

        if success:
            return 'json:', dict(success=True)
        return 'json:', dict(success=False,
                             message=_("Failure updating group"))

class GroupList(HTTPMethod):
    def get(self):
        if not is_administrator:
            raise HTTPNotFound

        groups = sorted(Group.objects(), key=lambda g: g.id)
        return 'brave.core.group.template.list_groups', dict(
            area='group',
            groups=groups,
        )

class GroupController(Controller):
    index = GroupList()

    def __lookup__(self, id, *args, **kw):
        request.path_info_pop()  # We consume a single path element.
        return OneGroupController(id), args

    @authorize(is_administrator)
    def create(self, id=None, title=None):
        if not id:
            return 'json:', dict(success=False,
                                 message=_("id required"))
        if not title:
            return 'json:', dict(success=False,
                                 message=_("title required"))
        g = Group.create(id, title, user)
        if not g:
            return 'json:', dict(success=False,
                                 message=_("group with that id already existed"))

        return 'json:', dict(success=True, id=g.id)
