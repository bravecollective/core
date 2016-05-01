from brave.core.character.model import EVEAlliance
from lxml import etree
import requests
import time

req = requests.get('https://api.eveonline.com/eve/AllianceList.xml.aspx')
root = etree.fromstring(req.text.encode("utf-8"))

for ally in EVEAlliance.objects(short=None):
    print(ally.name)
    query = root.xpath("/eveapi/result/rowset/row[@allianceID=" + str(ally.identifier) + "]")
    if not query:
        print("Negative, alliance is unknown")
        continue
    ticker = query[0].get('shortName')
    if not ticker:
        print("Ups, no ticker")
        continue
    print (ticker)
    ally.short = ticker
    ally.save()

