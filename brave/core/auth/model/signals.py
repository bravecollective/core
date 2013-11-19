# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime

from web.core import config
from mongoengine.signals import pre_save, post_save
from marrow.util.futures import ScalingPoolExecutor


validator_pool = ScalingPoolExecutor(5, 10, 60)


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



def validate_key(identifier):
    from adam.api import APICall
    from adam.auth.model.eve import EVECredential
    
    cred = EVECredential.objects.get(id=identifier)
    
    result = APICall.objects.get(name='account.APIKeyInfo')(cred)
    
    cred.mask = result.key['@accessMask']
    cred.kind = result.key['@type']
    cred.expires = datetime.strptime(result.key['@expires'], '%Y-%m-%d %H:%M:%S') if result.key.get('@expires', None) else None
    cred.verified = True
    cred.save()


@signal(post_save)
def trigger_api_validation(sender, document, **kwargs):
    if not kwargs.get('created', False):
        return
    
    if config.get('debug', False):
        validate_key(document.id)
    
    else:
        validator_pool.submit(validate_key, document.id)
