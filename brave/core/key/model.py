# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime
from mongoengine import Document, StringField, DateTimeField, BooleanField, ReferenceField, IntField

from brave.core.util.signal import update_modified_timestamp, trigger_api_validation


log = __import__('logging').getLogger(__name__)


@trigger_api_validation.signal
@update_modified_timestamp.signal
class EVECredential(Document):
    meta = dict(
            collection = "Credentials",
            allow_inheritance = False,
            indexes = [
                    'owner',
                    # Don't keep expired credentials.
                    dict(fields=['expires'], expireAfterSeconds=0)
                ],
        )
    
    key = IntField(db_field='k')
    code = StringField(db_field='c')
    kind = StringField(db_field='t')
    mask = IntField(db_field='a', default=0)
    verified = BooleanField(db_field='v', default=False)
    expires = DateTimeField(db_field='e')
    owner = ReferenceField('User', db_field='o', reverse_delete_rule='CASCADE')
    
    modified = DateTimeField(db_field='m', default=datetime.utcnow)
    
    @property
    def characters(self):
        from brave.core.character.model import EVECharacter
        return EVECharacter.objects(credential=self)
    
    def importChars(self):
        # TODO: Move into a background signal handler.
        from brave.core.util.eve import APICall
        from brave.core.character.model import EVEAlliance, EVECorporation, EVECharacter
        
        result = APICall.objects.get(name='account.APIKeyInfo')(self)
        key = result.key
        rows = key.rowset.row if isinstance(key.rowset.row, list) else [key.rowset.row]

        for row in rows:
            charID = row['@characterID']
            info = APICall.objects.get(name='eve.CharacterInfo')(self, characterID=charID)
            
            alliance, _ = EVEAlliance.objects.get_or_create(
                    name = info.alliance,
                    identifier = info.allianceID)
            
            corporation, _ = EVECorporation.objects.get_or_create(
                    name = info.corporation,
                    identifier = info.corporationID,
                    alliance = alliance
                )
            
            character = EVECharacter(
                    owner = self.owner,
                    credential = self,
                    name = info.characterName,
                    corporation = corporation,
                    alliance = alliance,
                    identifier = charID,
                )
            character.save()
