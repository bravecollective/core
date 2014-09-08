# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime

from web.auth import user
from web.core import Controller, HTTPMethod, request
from web.core.locale import _
from web.core.http import HTTPNotFound

from brave.core.group.model import Group
from brave.core.group.acl import ACLList, ACLKey, ACLTitle, ACLRole, ACLMask
from brave.core.util import post_only
from brave.core.permission.util import user_has_permission
from brave.core.permission.model import Permission, WildcardPermission, GRANT_WILDCARD

import json

log = __import__('logging').getLogger(__name__)


class OneGroupController(Controller):
    def __init__(self, id):
        super(OneGroupController, self).__init__()

        try:
            self.group = Group.objects.get(id=id)
        except Group.DoesNotExist:
            raise HTTPNotFound()

    @user_has_permission(Group.VIEW_PERM, group_id='self.group.id')
    def index(self):
        return 'brave.core.group.template.group', dict(
            area='group',
            group=self.group,
        )

    @post_only
    @user_has_permission(Group.EDIT_ACL_PERM, group_id='self.group.id')
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
                             
    @post_only
    @user_has_permission(Group.EDIT_PERMS_PERM, group_id='self.group.id')
    @user_has_permission(Permission.GRANT_PERM, permission_id='permission')
    def addPerm(self, permission=None):
        p = Permission.objects(id=permission)
        if len(p):
            p = p.first()
        else:
            if GRANT_WILDCARD in permission:
                p = WildcardPermission(permission)
            else:
                p = Permission(permission)
            p.save()
        self.group._permissions.append(p)
        self.group.save()
        
    @post_only
    @user_has_permission(Group.EDIT_PERMS_PERM, group_id='self.group.id')
    @user_has_permission(Permission.REVOKE_PERM, permission_id='permission')
    def deletePerm(self, permission=None):
        p = Permission.objects(id=permission).first()
        self.group._permissions.remove(p)
        self.group.save()

    @post_only
    @user_has_permission(Group.DELETE_PERM, group_id='self.group.id')
    def delete(self):
        self.group.delete()
        return 'json:', dict(success=True)


class GroupList(HTTPMethod):
    @user_has_permission('core.group.view.*', accept_any_matching=True)
    def get(self):
        groups = sorted(Group.objects(), key=lambda g: g.id)
        
        visibleGroups = list()
        for g in groups:
            if user.has_permission(g.view_perm):
                visibleGroups.append(g)
        
        return 'brave.core.group.template.list_groups', dict(
            area='group',
            groups=visibleGroups,
        )

    @user_has_permission(Group.CREATE_PERM)
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
                                 
        primary = user.primary if user.primary else user.characters[0]
        # Give the creator of the group the ability to edit it and delete it.
        editPerm = Permission(g.edit_acl_perm, "Ability to edit ACLs for Group {0}".format(g.id))
        editPermsPerm = Permission(g.edit_perms_perm, "Ability to edit permissions for Group {0}".format(g.id))
        deletePerm = Permission(g.delete_perm, "Ability to delete Group {0}".format(g.id))
        primary.personal_permissions.append(editPerm)
        primary.personal_permissions.append(deletePerm)
        primary.personal_permissions.append(editPermsPerm)
        user.save(cascade=True)
        
        return 'json:', dict(success=True, id=g.id)


class GroupController(Controller):
    index = GroupList()

    def __lookup__(self, id, *args, **kw):
        request.path_info_pop()  # We consume a single path element.
        return OneGroupController(id), args

    @user_has_permission('core.group.edit.*', accept_any_matching=True)
    def check_rule_reference_exists(self, kind, name):
        cls = ACLList.target_class(kind)
        return "json:", dict(exists=bool(cls.objects(name=name)))
