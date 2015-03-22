"""Imports and re-exports from evelink, setting the default cache."""

import pickle

import evelink

from datetime import datetime, timedelta, tzinfo
from mongoengine import Document, BinaryField, DateTimeField, StringField

class EvelinkAPICacheEntry(Document):
    meta = dict(
        indexes = [
            dict(
                fields = ['key'],
                unique = True,
            ),
            dict(
                fields = ['expireAt'],
                expireAfterSeconds = 0,
            ),
        ],
    )

    key = StringField()
    value = BinaryField()
    expireAt = DateTimeField()

class MongoCache(evelink.api.APICache):
    """Mongo-backed evelink APICache implementation"""

    def __init__(self):
        pass

    def get(self, key):
        """Return the value referred to by 'key' if it is cached.

        key:
            a string hash key
        """
        entry = EvelinkAPICacheEntry.objects(key=key).first()
        if not entry:
            return None
        if entry.expireAt < datetime.now(utc):
            # Mongo's expiration isn't immediate, so we'll check the
            # expiration time ourselves as well.
            entry.delete()
            return None
        return pickle.loads(entry.value)

    def put(self, key, value, duration):
        """Cache the provided value, referenced by 'key', for the given duration.

        key:
            a string hash key
        value:
            an xml.etree.ElementTree.Element object
        duration:
            a number of seconds before this cache entry should expire.
        """
        new_entry = EvelinkAPICacheEntry(
            key=key,
            value=pickle.dumps(value, 2),
            expireAt=datetime.now(utc) + timedelta(seconds=duration),
        )
        try:
            new_entry.save()
        except NotUniqueError:
            # We probably made this query twice at the same time. Hopefully CCP
            # isn't mad at us.
            pass

# Pasted from the datetime docs, because the python 2 datetime library is an
# embarrassment.

ZERO = timedelta(0)
HOUR = timedelta(hours=1)

# A UTC class.

class UTC(tzinfo):
    """UTC"""

    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO

utc = UTC()

# Here, finally, is where it happens: set the default cache and re-export.
evelink.api.default_cache = MongoCache()
from evelink import *  # noqa
__all__ = evelink.__all__
