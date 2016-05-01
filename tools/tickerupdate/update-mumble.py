from brave.mumble.auth.model import Ticket
from web.core import config
from brave.api.client import API

import time
api = API(config['api.endpoint'], config['api.identity'], config['api.private'], config['api.public'])

aids = set()
for t in Ticket.objects(alliance__ticker=None):
    if t.alliance.name:
        aids.add(t.alliance.id)

for aid in aids:
    time.sleep(1)
    print("\nAlliance: {0}".format(aid))
    alliance = api.lookup.alliance(aid, only='short')
    if not alliance or not alliance.success or not alliance.short:
        continue
    print("Short: {0}".format(alliance.short))
    for t in Ticket.objects(alliance__id=aid):
        t.alliance.ticker = alliance.short
        t.save()

cids = set()
for t in Ticket.objects(corporation__ticker=None):
    if t.corporation.name:
        cids.add(t.corporation.id)

for cid in cids:
    time.sleep(1)
    print("\nCorporation: {0}".format(cid))
    corporation = api.lookup.corporation(cid, only='short')
    if not corporation or not corporation.success or not corporation.short:
        continue
    print("Short: {0}".format(corporation.short))
    for t in Ticket.objects(corporation__id=cid):
        t.corporation.ticker = corporation.short
        t.save()

