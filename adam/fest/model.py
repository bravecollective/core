# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime

from mongoengine import Document, StringField, DateTimeField, BooleanField, ReferenceField, IntField, FloatField

from adam.auth.model.eve import EVECredential
from adam.auth.model.signals import update_modified_timestamp


@update_modified_timestamp.signal
class DonationDrive(Document):
    meta = dict(
            collection = "DonationDrives",
            allow_inheritance = False,
        )
    
    total = FloatField(db_field='t', default=0)
    credential = ReferenceField(EVECredential, db_field='r')
    character = IntField(db_field='c')
    modified = DateTimeField(db_field='m', default=datetime.utcnow)
    
    @property
    def latest(self):
        return EVEDonation.objects(drive=self).limit(30).order_by('-date')
    
    @property
    def count(self):
        return EVEDonation.objects(drive=self).count()


class EVEDonation(Document):
    meta = dict(
            collection = "Donations",
            allow_inheritance = False,
            indexes = [
                    ('drive', '-date'),
                ],
        )
    
    REFTYPE = 10  # Fixed value.
    
    drive = ReferenceField(DonationDrive, db_field='dr')
    
    date = DateTimeField(db_field='d')
    ref = IntField(db_field='r', unique=True)
    amount = FloatField(db_field='a')
    who = StringField(db_field='w')  # ownerName1
    whoId = IntField(db_field='wi')
    comment = StringField(db_field='c')  # reason
