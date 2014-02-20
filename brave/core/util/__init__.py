# encoding: utf-8

from __future__ import unicode_literals

import re
from HTMLParser import HTMLParser
from marrow.util.object import load_object
from web.auth import always


def load(area):
    return load_object("brave.core.{}.controller:{}Controller".format(area, area.title()))()


class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []
    
    def handle_data(self, d):
        self.fed.append(d)
    
    def get_data(self):
        return ''.join(self.fed)


def strip_tags(html):
    txt = re.sub('<[^>]+>', '', html)
    return re.sub('\s+', ' ', txt)
    
    #s = MLStripper()
    #s.feed(html)
    #return s.get_data()


def require(*predicates):
    def conditional(*args, **kw):
        for predicates, handler in conditional.handlers:
            if not all(predicates):
                continue
            
            return handler(*args, **kw)
            
        else:
            raise HTTPNotFound
    
    def require(*predicates):
        def decorator(fn):
            conditional.append((predicates, fn))
            return conditional
        
        return decorator
    
    def otherwise(fn):
        conditional.handlers.append(((always, ), fn))
        return conditional
    
    conditional.handlers = []
    conditional.require = require
    conditional.otherwise = otherwise
    
    def decorator(fn):
        conditional.handlers.append((predicates, fn))
        return conditional
    
    return decorator
