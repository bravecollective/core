# encoding: utf-8

from __future__ import unicode_literals

from web.auth import always
from web.core import request, HTTPMethod
from web.core.http import HTTPNotFound
from web.core.locale import _

from marrow.schema.declarative import BaseAttribute, Attribute


log = __import__('logging').getLogger(__name__)


class ActionController(HTTPMethod):
    __slots__ = ()
    
    def __call__(self, *args, **kw):
        if hasattr(self.action, 'condition'):
            if not self.action.condition:
                log.error("Attempt to access %r whose condition fails.", self)
                raise HTTPNotFound()
        
        return super(ActionController, self).__call__(*args, **kw)
    
    def __repr__(self):
        return b"{0}({1})".format(
                self.__class__.__name__,
                self.action.title
            )


class Action(BaseAttribute):
    get = Attribute()
    title = Attribute()
    instance = Attribute(default=True)
    icon = Attribute(default=None)
    
    template = Attribute()
    condition = Attribute(default=always)
    
    # More specific actions may be defined.
    post = Attribute(default=None)
    delete = Attribute(default=None)
    
    def clone(self, **kwargs):
        instance = self.__class__()
        instance.__data__ = self.__data__.copy()
        
        for name, value in kwargs.iteritems():
            setattr(instance, name, value)
        
        return instance
    
    @classmethod
    def method(cls, *args, **kw):
        def inner(fn):
            return cls(fn, *args, **kw)
        
        return inner
    
    def bind(self, kind):
        def inner(fn):
            setattr(self, kind, fn)
            return self
        
        return inner
    
    @property
    def controller(self):
        data = dict(action=self, get=self.get)
        
        for i in 'post', 'delete':
            if getattr(self, i):
                data[i] = getattr(self, i)
        
        # Dynamically construct a new HTTPMethod class.
        return type(b"{0}ActionController".format(self.__name__.replace('_', ' ').title().replace(' ', '')), (ActionController, ), data)
