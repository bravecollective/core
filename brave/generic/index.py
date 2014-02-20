# encoding: utf-8

from __future__ import unicode_literals

from marrow.schema.declarative import BaseAttribute, Attribute


log = __import__('logging').getLogger(__name__)


class Index(BaseAttribute):
    attribute = Attribute()
    keys = Attribute(default=None)
    order = Attribute(default='asc')  # asc or desc
    
    @property
    def terms(self):
        attribute = self.attribute.replace('.', '__') + '__icontains'
        
        if self.keys:
            for key in self.keys:
                yield (attribute + '.' + key + '__icontains')
        
        yield attribute
