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
from brave.core.util import post_only
from brave.core.util.predicate import authorize, is_administrator

import json

log = __import__('logging').getLogger(__name__)

class OneGroupController(Controller):
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

    @authorize(is_administrator)
    @post_only
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
    @post_only
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

    @authorize(is_administrator)
    def post(self, id=None, title=None):
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

class GroupController(Controller):
    index = GroupList()

    def __lookup__(self, id, *args, **kw):
        request.path_info_pop()  # We consume a single path element.
        return OneGroupController(id), args

    @authorize(is_administrator)
    def check_rule_reference_exists(self, kind, name):
        cls = ACLList.target_class(kind)
        return "json:", dict(exists=bool(cls.objects(name=name)))
