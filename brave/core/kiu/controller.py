# encoding: utf-8

from web.core import Controller, HTTPMethod, request, config
from web.core.http import HTTPNotFound, HTTPForbidden, HTTPBadRequest
from brave.core.character.model import EVECharacter


class GroupLookupInterface(HTTPMethod):
    def __init__(self, charid, secret):
        super(GroupLookupInterface, self).__init__()

    def get(self, charid=None, secret=None):
        if not secret or not charid:
            raise HTTPBadRequest

        # this is a dirty hack and kiu is to blame
        if secret != config['kiu.secret']:
            raise HTTPForbidden

        if not charid.isdigit():
            raise HTTPBadRequest

        c = EVECharacter.objects(identifier=charid).first()

        if not c:
            return 'json:', dict(name='', groups='', tags='', perms='')

        groups = []
        for g in c.groups:
            groups.append(g.id)

        perms = []
        for p in c.permissions():
            perms.append(p.id)

        tags = []
        for t in c.tags:
            tags.append(t)

        return 'json:', dict(name=c.name, groups=groups, tags=tags,
                             perms=perms)


class KiuController(Controller):
    def __lookup__(self, charid, secret, *args, **kw):
        request.path_info_pop()  # We consume a single path element.
        return GroupLookupInterface(charid, secret), args
