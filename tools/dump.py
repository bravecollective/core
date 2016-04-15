# encoding: utf-8

from __future__ import print_function

from json import dump

from brave.core.account.model import User
from brave.core.account.model import LoginHistory
from brave.core.character.model import EVECharacter
from brave.core.util.eve import api

c=dict(users=dict(), characters=dict())

for u in User.objects.all():
    uname = u.username.encode('ascii', 'backslashreplace')
    c['users'][uname] = dict(id=str(u.id), email=u.email, credentials=dict(), characters=list())
    c['users'][uname]['credentials'] = {i.key: dict(code=i.code, kind=i.kind, mask=i.mask, verified=i.verified, expires=(i.expires.strftime('%y-%m-%d %H:%M:%S') if i.expires else None)) for i in u.credentials}
    c['users'][uname]['characters'] = {i.identifier: dict(name=i.name, corporation=(i.corporation.name if i.corporation else None), alliance=(i.alliance.name if i.alliance else None)) for i in u.characters}
    c['users'][uname]['ips'] = list(set([i.location for i in LoginHistory.objects(user=u).only('location')]))
    print('user {0} with {1} credentials and {2} characters'.format(uname, len(c['users'][uname]['credentials']), len(c['users'][uname]['characters'])))

for char in EVECharacter.objects.all():
    c['characters'][char.name] = dict(corporation=(char.corporation.name if char.corporation else None), alliance=(char.alliance.name if char.alliance else None))
    c['characters'][char.name]['credentials'] = {}
    try:
        for i in char.credentials:
            c['characters'][char.name]['credentials'][i.key] = dict(code=i.code, kind=i.kind, mask=i.mask, verified=i.verified, expires=(i.expires.strftime('%y-%m-%d %H:%M:%S') if i.expires else None))
    except:
        c['characters'][char.name]['credentials']['broken'] = True
    try:
        c['characters'][char.name]['owner'] = char.owner.username
    except:
        c['characters'][char.name]['owner'] = '!!!ORPHAN!!!'
    c['characters'][char.name]['titles'] = char.titles
    c['characters'][char.name]['roles'] = char.roles
    print('character', char.name)


c['roles'] = dict()

for r in EVECharacter.objects.distinct('roles'):
    c['roles'][r] = dict()
    for char in EVECharacter.objects(roles=r):
        c['roles'][r][char.name] = dict(corporation=(char.corporation.name if char.corporation else None), alliance=(char.alliance.name if char.alliance else None))
    print('role', r)

c['titles'] = dict()

for r in EVECharacter.objects.distinct('titles'):
    c['titles'][r] = dict()
    for char in EVECharacter.objects(titles=r):
        c['titles'][r][char.name] = dict(corporation=(char.corporation.name if char.corporation else None), alliance=(char.alliance.name if char.alliance else None))
    print('title', r)


print('dumping')
with open('/home/core/dump.json', 'w') as a:
    dump(c, a, indent=4, sort_keys=True, separators=(',', ': '))
print('done')
