# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime

from web.auth import user
from web.core import Controller, HTTPMethod, request
from web.core.locale import _
from web.core.http import HTTPFound, HTTPNotFound

from brave.core.character.model import EVECharacter, EVECorporation, EVEAlliance
from brave.core.group.model import Group
from brave.core.group.acl import ACLList, ACLKey, ACLTitle, ACLRole, ACLMask
from brave.core.util.predicate import authorize, is_administrator

import json

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


        r = self.group.rules[-1] if len(self.group.rules) else None
        if not r or not (isinstance(r, ACLList) and r.grant and not r.inverse and r.kind == 'c'):
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

        r = self.group.rules[-1] if len(self.group.rules) else None
        if not r or not (isinstance(r, ACLList) and r.grant and not r.inverse and r.kind == 'c'):
            return 'json:', dict(success=False,
                                 message=_("Sorry, I don't know what to do!"))
        if not c.identifier in r.ids:
            return 'json:', dict(success=False,
                                 message=_("Character not found in last rule!"))
        r.ids.remove(c.identifier)
        if not r.ids:
            # If we just removed the last user in the rule, get rid of the rule.
            self.group.rules.pop(-1)
        success = self.group.save()

        if success:
            return 'json:', dict(success=True)
        return 'json:', dict(success=False,
                             message=_("Failure updating group"))

    @authorize(is_administrator)
    def set_rules(self, rules, really=False):
        rules = json.loads(rules)
        rule_objects = []
        log.debug(rules)
        log.debug(really)

        def listify(rule, field):
            if field not in rule:
                rule[field] = []
            elif not isinstance(r[field], list):
                rule[field] = [rule[field]]

        for r in rules:
            grant = r['grant'] == "true"
            inverse = r['inverse'] == "true"
            if r['type'] == "list":
                listify(r, 'names')
                cls = ACLList.target_class(r['kind'])
                ids = [cls.objects(name=name).first().identifier for name in r['names']]
                rule_objects.append(ACLList(grant=grant, inverse=inverse, kind=r['kind'], ids=ids))
            elif r['type'] == "key":
                rule_objects.append(ACLKey(grant=grant, inverse=inverse, kind=r['kind']))
            elif r['type'] == "title":
                listify(r, 'titles')
                rule_objects.append(ACLTitle(grant=grant, inverse=inverse, titles=r['titles']))
            elif r['type'] == "role":
                listify(r, 'roles')
                rule_objects.append(ACLRole(grant=grant, inverse=inverse, roles=r['roles']))
            elif r['type'] == "mask":
                rule_objects.append(ACLMask(grant=grant, inverse=inverse, mask=r['mask']))

        log.debug(rule_objects)

        if not really:
            log.debug("not really")
            return "json:", "\n".join([r.human_readable_repr() for r in rule_objects])

        log.debug("really!")
        self.group.rules = rule_objects
        success = self.group.save()
        log.debug(success)
        if success:
            return 'json:', dict(success=True)
        return 'json:', dict(success=True,
                             message=_("unimplemented"))

    @authorize(is_administrator)
    def delete(self):
        self.group.delete()
        return 'json:', dict(success=True)

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
    def check_rule_reference_exists(self, kind, name):
        cls = ACLList.target_class(kind)
        return "json:", dict(exists=bool(cls.objects(name=name)))

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
