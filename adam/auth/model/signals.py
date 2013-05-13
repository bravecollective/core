# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime

from mongoengine.signals import pre_save, post_save


def signal(event):
    def decorator(fn):
        def connect(model):
            event.connect(fn, sender=model)
        
        def signal(cls):
            event.connect(fn, sender=cls)
            return cls
        
        fn.connect = connect
        fn.signal = signal
        return fn
    
    return decorator


@signal(pre_save)
def update_modified_timestamp(sender, document, **kwargs):
    document.modified = datetime.utcnow()


@signal(post_save)
def trigger_api_validation(sender, document, **kwargs):
    if not kwargs.get('created', False):
        return
    
    pass # Do something!  :D
