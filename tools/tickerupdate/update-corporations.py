from brave.core.character.model import EVECorporation
from lxml import etree
import requests
import time

i = 0
for corp in EVECorporation.objects(short=None):
    time.sleep(1)
    i = i + 1
    print("{0} {1}".format(i, corp.name))
    req = requests.get('https://api.eveonline.com/corp/CorporationSheet.xml.aspx?corporationID=' + str(corp.identifier))
    root = etree.fromstring(req.text.encode("utf-8"))
    query = root.xpath("/eveapi/result/ticker")
    if not query:
        print("Nope, corp not found")
        continue
    ticker = query[0].text
    if not ticker:
        print("Ups, no ticker")
        continue
    print (ticker)
    corp.short = ticker
    corp.save()

