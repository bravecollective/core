# encoding: utf-8

from datetime import datetime
from web.core import Controller, request

from adam.fest.model import DonationDrive, EVEDonation
from adam.api import APICall


class RootController(Controller):
    def index(self):
        print(self.refresh())
        
        return "adam.fest.template.home", dict(
                drive = DonationDrive.objects.first()
            )
    
    def refresh(self):
        drive = DonationDrive.objects.first()
        call = APICall.objects.get(name='char.WalletJournal')
        
        last = drive.latest.first()
        
        if not last:
            result = call(drive.credential,
                    characterID=drive.character,
                    rowCount=2560,
                )
        else:
            result = call(drive.credential,
                    characterID=drive.character,
                    rowCount=2560,
                    fromID=last.ref
                )
        
        if 'transactions' not in result.rowset:
            # from pprint import pprint
            # pprint(result)
            return "Nothing new: %d donation(s), %0.2f total." % (EVEDonation.objects(drive=drive).count(), drive.total)
        
        # from pprint import pprint
        # pprint([dict(i) for i in result.rowset.transactions])
        
        for row in result.rowset.transactions:
            if int(row['@refTypeID']) != EVEDonation.REFTYPE:
                # Ignore non-donation values.
                continue
            
            if int(row['@ownerID2']) != drive.character:
                # Ignore donations to other players exposed by the key.
                continue
            
            try:
                donation = EVEDonation(
                        drive = drive,
                        date = datetime.strptime(row['@date'], '%Y-%m-%d %H:%M:%S'),
                        ref = int(row['@refID']),
                        amount = float(row['@amount']),
                        who = row['@ownerName1'],
                        whoId = row['@ownerID1'],
                        comment = row['@reason'],
                    )
                donation.save()
            except:
                raise
            else:
                drive.update(inc__total=donation.amount)
        
        drive.reload()
        
        return "Updated: %d donation(s), %0.2f total." % (EVEDonation.objects(drive=drive).count(), drive.total)
