from bson import ObjectId, DBRef
from brave.core.key.model import EVECredential
from brave.core.character.model import EVECharacter

orphaned_keys_char = set()
chars = EVECharacter.objects()
for char in chars:
    for cr in char.credentials:
        if isinstance(cr, DBRef):
            #char.credentials = []
            #char.save()
            orphaned_keys_char.add(char)

orphaned_keys_char

for char in orphaned_keys_char:
    char.credentials = []
    char.save()

