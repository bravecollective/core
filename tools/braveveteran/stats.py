from brave.core.character.model import EVECharacter
from brave.core.key.model import EVECredential
from brave.core.group.model import Group
from brave.core.permission.model import Permission

import datetime
import time
import requests
from lxml import etree
import math

print()

cache = []

def get_group(gid, age):
    g = Group.objects(id=gid)[0]
    for r in g.rules:
	if r.kind == 'c':
	    return {'group': g, 'rule': r, 'age': age}
    return

def download(url):
    while 1:
	try:
	    return requests.get(url, timeout=10)
	except:
	    print('Failed: {0}'.format(url))
	    time.sleep(20)

def retrieve(cid):
    for c in cache:
	if c['character_id'] == cid:
	    print("CACHE: {0}".format(c))
	    return c
    time.sleep(1)
    result = {'character_id': cid, 'character_name': '', 'age': -1}
    req = download('https://api.eveonline.com/eve/CharacterInfo.xml.aspx?characterID={0}'.format(cid))
    root = etree.fromstring(req.text.encode("utf-8"))
    result['character_name'] = root.xpath("/eveapi/result/characterName")[0].text
    bd = root.xpath("/eveapi/result/corporationDate")[0].text
    result['age'] = int(math.floor((datetime.datetime.now() - datetime.datetime.strptime(bd, "%Y-%m-%d %H:%M:%S")).days / 365))
    cd = root.xpath("/eveapi/result/corporationID")[0].text
    if cd != '98169165':
	result['age'] = -1
    cache.append(result)
    return result

def clean(gd):
    print("Cleaning: {0}".format(gd['group'].id))
    results = []
    r = gd['rule']
    for cid in r.ids:
	results.append(retrieve(cid))
    for result in results:
	if result['age'] != gd['age']:
	    r.ids.remove(result['character_id'])
	    print("DELE: {0}".format(result))
	else:
	    print("KEEP: {0}".format(result))
    gd['group'].save()


groups = []
groups.append(get_group('alliance.corporation.bni.veterans.a.year.of.living.dangerously', 1))
groups.append(get_group('alliance.corporation.bni.veterans.two.brave.to.die', 2))
groups.append(get_group('alliance.corporation.bni.veterans.threepeatedly.brave', 3))


print("Cleaning....")
for g in groups:
    clean(g)

print("Downloading....")
for c in EVECharacter.objects():
    if not c.corporation:
        continue
    if c.corporation.identifier != 98169165:
        continue
    for cred in c.credentials:
        if not type(cred) is EVECredential:
            continue;
	retrieve(c.identifier)

groups = []
groups.append(get_group('alliance.corporation.bni.veterans.a.year.of.living.dangerously', 1))
groups.append(get_group('alliance.corporation.bni.veterans.two.brave.to.die', 2))
groups.append(get_group('alliance.corporation.bni.veterans.threepeatedly.brave', 3))

print("Updating....")
for c in cache:
    for g in groups:
	if c['age'] == g['age']:
	    r = g['rule']
	    if c['character_id'] not in r.ids:
		r.ids.append(c['character_id'])

print("Saving....")
for g in groups:
    g['group'].save()


