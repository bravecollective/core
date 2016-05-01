# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime
from collections import OrderedDict

from web.auth import user
from web.core import Controller, HTTPMethod, request
from web.core.locale import _
from web.core.http import HTTPNotFound

from brave.core.character.model import EVECharacter
from brave.core.group.model import Group, GroupCategory
from brave.core.group.acl import ACLList, ACLKey, ACLTitle, ACLRole, ACLMask, ACLVerySecure, ACLGroupMembership, CyclicGroupReference
from brave.core.util import post_only
from brave.core.util.predicate import authenticate
from brave.core.permission.util import user_has_permission, user_has_any_permission
from brave.core.permission.model import Permission, WildcardPermission, GRANT_WILDCARD

import json

log = __import__('logging').getLogger(__name__)


class OneGroupController(Controller):
    @authenticate
    def __init__(self, id):
        super(OneGroupController, self).__init__()

        try:
            self.group = Group.objects.get(id=id)
        except Group.DoesNotExist:
            raise HTTPNotFound()

        if not user or not user.has_permission(self.group.view_perm):
            raise HTTPNotFound()
    
    @post_only
    @user_has_permission(Group.EDIT_REQUESTS_PERM, group_id='self.group.id')
    def accept_request(self, name):
        c = EVECharacter.objects(name__iexact=name.strip()).first()
        if not c:
            return 'json:', dict(success=False, message=_("Character with that name not found."))
            
        if not c in self.group.requests:
            return 'json:', dict(success=False, message=_("Character with that name has no request to join this group."))
        
        log.info("Adding {0} to group {1} via REQUEST_ACCEPT approved by {2}".format(c.name, self.group.id, user.primary))
        self.group.add_request_member(c)
        self.group.requests.remove(c)
        self.group.save()
        
        return 'json:', dict(success=True)
    
    @post_only
    @user_has_permission(Group.EDIT_REQUESTS_PERM, group_id='self.group.id')
    def deny_request(self, name):
        c = EVECharacter.objects(name__iexact=name.strip()).first()
        if not c:
            return 'json:', dict(success=False, message=_("Character with that name not found."))
            
        if not c in self.group.requests:
            return 'json:', dict(success=False, message=_("Character with that name has no request to join this group."))
        
        log.info("Rejecting {0}'s application to group {1} via REQUEST_DENY by {2}".format(c.name, self.group.id, user.primary))
        self.group.requests.remove(c)
        self.group.save()
        
        return 'json:', dict(success=True)
    
    @post_only
    @user_has_permission(Group.EDIT_MEMBERS_PERM, group_id='self.group.id')
    def kick_member(self, name, method):
        char_list = {
            "join": self.group.join_members,
            "request": self.group.request_members,
        }[method]
        c = EVECharacter.objects(name__iexact=name.strip()).first()
        if not c:
            return 'json:', dict(success=False, message=_("Character with that name not found."))
            
        if not c in char_list:
            return 'json:', dict(success=False, message=_("Character with that name is not a member via that method."))
            
        log.info("Removing {0} from group {1} (admitted via {2}) via KICK_MEMBER by {3}".format(c.name, self.group.id, method, user.primary))
        char_list.remove(c)
        self.group.save()
        
        return 'json:', dict(success=True)

    @user_has_permission(Group.VIEW_PERM, group_id='self.group.id')
    def index(self, rule_set=None):
        return 'brave.core.group.template.group', dict(
            area='group',
            admin=user.admin,
            group=self.group,
            rule_set=rule_set,
        )

    @post_only
    @user_has_permission(Group.EDIT_ACL_PERM, group_id='self.group.id')
    def set_rules(self, rules, really=False, rule_set=None):
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
                cls = ACLList.KIND_CLS[r['kind']]
                ids = [cls.objects(name__iexact=name.strip()).first().identifier for name in r['names']]
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
            elif r['type'] == "verysecure":
                rule_objects.append(ACLVerySecure(grant=grant, inverse=inverse))
            elif r['type'] == "groupmembership":
                g = Group.objects(id=r['group']).first()
                if not g:
                    # TODO: change dry-run to return a success/fail format so the UI here is better
                    return 'json:', dict(success=False,
                                         message="ERROR: Couldn't find group {}!!".format(r['group']))
                rule_objects.append(ACLGroupMembership(grant=grant, inverse=inverse, group=g))

        log.debug(rule_objects)

        if rule_set == "request":
            self.group.request_rules = rule_objects
        elif rule_set == "join":
            self.group.join_rules = rule_objects
        else:
            self.group.rules = rule_objects

        try:
            self.group.cycle_check()
        except CyclicGroupReference as e:
            return 'json:', dict(success=False,
                                 message="Circular group reference: {}".format(e.cycle))

        if not really:
            log.debug("not really")
            return "json:", dict(success=True,
                                 message="\n".join([unicode(r) for r in rule_objects]))

        log.debug("really!")
        success = self.group.save()
        log.debug(success)
        if success:
            return 'json:', dict(success=True)
        return 'json:', dict(success=False,
                             message=_("unimplemented"))
                             
    @post_only
    @user_has_permission(Group.EDIT_PERMS_PERM, group_id='self.group.id')
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
        self.group._permissions.append(p)
        self.group.save()
        
        return 'json:', dict(success=True)
        
    @post_only
    @user_has_permission(Group.EDIT_PERMS_PERM, group_id='self.group.id')
    @user_has_permission(Permission.REVOKE_PERM, permission_id='permission')
    def delete_perm(self, permission=None):
        p = Permission.objects(id=permission).first()
        self.group._permissions.remove(p)
        self.group.save()
        
        return 'json:', dict(success=True)

    @post_only
    @user_has_permission(Group.DELETE_PERM, group_id='self.group.id')
    def delete(self):
        try:
            self.group.delete()
        except Exception as e:
            return 'json:', dict(success=False, message=unicode(e))
        return 'json:', dict(success=True)

    @post_only
    @user_has_permission(Group.EDIT_TITLE_PERM, group_id='self.group.id')
    def set_title(self, title):
        log.info("'{0}' changed the title for group '{1}' from '{2}' to '{3}'".format(user.username, self.group.id, self.group.title, title))
        self.group.title = title
        self.group.save()

    @post_only
    @user_has_permission(Group.EDIT_ID_PERM, group_id='self.group.id')
    def set_id(self, new_id):
        log.info("'{0}' changed the id for group '{1}' from '{2}' to '{3}'".format(user.username, self.group.id, self.group.id, new_id))

        self.group = self.group.rename(new_id)


class GroupList(HTTPMethod):
    @authenticate
    def get(self):
        if not user:
            raise HTTPNotFound()

        groups = sorted(Group.objects(), key=lambda g: g.id)
        
        visibleGroups = list()
        joinableGroups = list()
        requestableGroups = list()
        
        if not user.primary:
            return 'brave.core.group.template.list_groups', dict(
            area='group',
            groups=visibleGroups
        )
        
        for g in groups:
            if g.evaluate(user, user.primary, rule_set="main"):
                continue
            elif g.evaluate(user, user.primary, rule_set='join'):
                joinableGroups.append(g)
                visibleGroups.append(g)
            elif g.evaluate(user, user.primary, rule_set='request'):
                requestableGroups.append(g)
                visibleGroups.append(g)
        
        return 'brave.core.group.template.list_groups', dict(
            area='group',
            groups=visibleGroups,
            joinableGroups=joinableGroups,
            requestableGroups=requestableGroups,
            categories=GroupCategory.objects(members__in=visibleGroups),
        )
        
    def leave(self, group):
        log.info("Removing {0} from group {1} via LEAVE.".format(user.primary, group.id))
        if user.primary in group.join_members:
            group.join_members.remove(user.primary)
        if user.primary in group.request_members:
            group.request_members.remove(user.primary)
            
        group.save()
        return 'json:', dict(success=True)
        
    def join(self, group):
        if not group.evaluate(user, user.primary, rule_set='join'):
            return 'json:', dict(success=False, message=_("You do not have permission to join this group."))
        
        log.info("Adding {0} to group {1} via JOIN.".format(user.primary, group.id))
        group.add_join_member(user.primary)
        
        group.save()
        return 'json:', dict(success=True)
        
    def request(self, group):
        if not group.evaluate(user, user.primary, rule_set='request'):
            return 'json:', dict(success=False, message=_("You do not have permission to request access to this group."))
        
        log.info("Adding {0} to requests list of {1} via REQUEST.".format(user.primary, group.id))
        group.add_request(user.primary)
        
        group.save()
        return 'json:', dict(success=True)
        
    def withdraw(self, group):
        log.info("Removing {0} from requests list of {1} via WITHDRAW.".format(user.primary, group.id))
        group.requests.remove(user.primary)
        
        group.save()
        return 'json:', dict(success=True)

    @authenticate
    def post(self, id=None, action=None):
        if not action:
            return 'json:', dict(success=False)
        else:
            group = Group.objects(id=id).first()
            
            if not group:
                return 'json:', dict(success=False, message=_("Group not found"))
            
            return {
                "leave": self.leave,
                "join": self.join,
                "request": self.request,
                "withdraw": self.withdraw,
            }[action](group)

class ManageGroupList(HTTPMethod):
    @user_has_any_permission('core.group.view.*')
    def get(self):
        groups = sorted(Group.objects(), key=lambda g: g.id)
        
        visibleGroups = list()
        
        user_perms = user.permissions
        
        for g in groups:
            if Permission.set_grants_permission(user_perms, g.view_perm):
                visibleGroups.append(g)
        
        return 'brave.core.group.template.manage_groups', dict(
            area='group',
            groups=visibleGroups
        )

    @user_has_permission(Group.CREATE_PERM)
    def post(self, id=None, title=None):
        if not id:
            return 'json:', dict(success=False,
                                 message=_("id required"))
                                 
        if id == 'manange':
            return 'json:', dict(success=False,
                                 message=_("You cannot name a group 'manage'"))
        if not title:
            return 'json:', dict(success=False,
                                 message=_("title required"))
        g = Group.create(id, title, user)
        if not g:
            return 'json:', dict(success=False,
                                 message=_("group with that id already existed"))
                                 
        primary = user.primary if user.primary else user.characters[0]
        # Give the creator of the group the ability to edit it and delete it.
        editPerm = Permission(g.edit_acl_perm, "Ability to edit ACLs for Group {0}".format(g.id)).save()
        editPermsPerm = Permission(g.edit_perms_perm, "Ability to edit permissions for Group {0}".format(g.id)).save()
        deletePerm = Permission(g.delete_perm, "Ability to delete Group {0}".format(g.id)).save()
        primary.personal_permissions.append(editPerm)
        primary.personal_permissions.append(deletePerm)
        primary.personal_permissions.append(editPermsPerm)
        primary.save()
        user.save()
        
        return 'json:', dict(success=True, id=g.id)


class GroupController(Controller):
    index = GroupList()
    manage = ManageGroupList()

    def __lookup__(self, id, *args, **kw):
        request.path_info_pop()  # We consume a single path element.
        return OneGroupController(id), args

    @user_has_any_permission('core.group.edit.*')
    def check_rule_reference_exists(self, kind, name):
        cls = ACLList.KIND_CLS[kind]
        return "json:", dict(exists=bool(cls.objects(name__iexact=name.strip())))
