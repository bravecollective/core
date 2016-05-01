from brave.core.character.model import EVECharacter
from brave.core.key.model import EVECredential
import operator
import datetime

today = datetime.date.today()
masks = {}
masks_user = {}

ages = {}
ages_user = {}

creds = set()
for c in EVECharacter.objects():
    if not c.corporation:
        continue
    if c.corporation.identifier != 98319972:
        continue
    for cred in c.credentials:
        if not type(cred) is EVECredential:
            continue;
        creds.add(cred)

for cred in creds:
    m = cred.mask.mask
    if not m in masks:
        masks[m] = 0
        masks_user[m] = set()
    masks[m] = masks[m] + 1
    if cred.owner.primary:
        masks_user[m].add(str(cred.owner.primary.name))
    else:
        masks_user[m].add(str(cred.owner.characters.first().name))
    
    a = (today - cred.id.generation_time.date()).days
    if not a in ages:
        ages[a] = 0
        ages_user[a] = set()
    ages[a] = ages[a] + 1
    if cred.owner.primary:
        ages_user[a].add(str(cred.owner.primary.name))
    else:
        ages_user[a].add(str(cred.owner.characters.first().name))

print("---- API KEY MASK: mask --> amount")
masks_sorted = sorted(masks.items(), key=operator.itemgetter(0))
for keys,values in masks_sorted:
    print("{0} --> {1}".format(keys, values))
    print("Characters: {0}".format(masks_user[keys]))
    print("");

print("---- API KEY AGE: days --> amount")
ages_sorted = sorted(ages.items(), key=operator.itemgetter(0))
for keys,values in ages_sorted:
    print("{0} --> {1}".format(keys, values))
    print("Characters: {0}".format(ages_user[keys]))
    print("");

print("done")


