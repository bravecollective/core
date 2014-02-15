# encoding: utf-8

from __future__ import unicode_literals

from operator import __or__

from datetime import datetime
from web.core import request, response, url, config
from web.auth import user
from mongoengine import Q
from marrow.util.url import URL
from marrow.util.object import load_object as load
from marrow.util.convert import boolean
from marrow.util.bunch import Bunch

from brave.core.util.eve import api
from brave.core.api.util import SignedController
from brave.core.character.model import EVEEntity, EVEAlliance, EVECorporation, EVECharacter
from web.core import cache


log = __import__('logging').getLogger(__name__)


_mapping = dict(identifier='id')


class LookupAPI(SignedController):
    def _only(self, data, only):
        if not only: return data
        only = only if isinstance(only, list) else [only]
        return dict({k: v for k, v in data.iteritems() if k == 'success' or k in only})
    
    def _lookup(self, cls, search, fields):
        #@cache.cache('api.lookup', expires=300)  # five minute expiry
        def inner(cls, search):
            record = cls.get(search)
            if not record: return dict(success=False, message="No matching record found.")
            
            result = Bunch(success=True)
            
            def process(value):
                if isinstance(value, EVEEntity):
                    if cls is EVEAlliance and isinstance(value, EVECorporation):
                        return dict(id=value.identifier, name=value.name, joined=process(value.joined))
                    return dict(id=value.identifier, name=value.name)
                if hasattr(value, 'strftime'):
                    return value.strftime('%y-%m-%d %H:%M:%S')
                if isinstance(value, list) or hasattr(value, '__iter__'):
                    return [process(i) for i in value]
                return value
            
            for field in fields:
                result[_mapping.get(field, field)] = process(getattr(record, field))
            
            return result
        
        return inner(cls, search)
    
    def alliance(self, search, only=None):
        return self._only(self._lookup(EVEAlliance, search, [
                'identifier', 'name', 'short', 'members', 'founded', 'corporations', 'executor'
            ]), only)
    
    def corporation(self, search, only=None):
        return self._only(self._lookup(EVECorporation, search, [
                'identifier', 'name', 'short', 'members', 'founded', 'alliance'
            ]), only)
    
    def character(self, search, only=None):
        return self._only(self._lookup(EVECharacter, search, [
                'identifier', 'name', 'race', 'bloodline', 'ancestry', 'gender', 'security', 'titles', 'corporation', 'alliance'
            ]), only)
