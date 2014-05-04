# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime

from web.core import Controller
from mongoengine.signals import pre_save, post_save
from marrow.util.futures import ScalingPoolExecutor
from marrow.util.bunch import Bunch
from marrow.mailer import Mailer
from requests.exceptions import HTTPError
from web.core import config

from brave.core import util


log = __import__('logging').getLogger(__name__)
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


class StartupMixIn(Controller):
    """The constructor of this class is called once upon application start."""
    
    def __init__(self):
        super(StartupMixIn, self).__init__()
        
        util.mail = Mailer(config, 'mail')
        util.mail.start()


@signal(pre_save)
def update_modified_timestamp(sender, document, **kwargs):
    """Automatically maintain a "last modification" date."""
    
    document.modified = datetime.utcnow()


# TODO: Move this to a more appropriate place.
def validate_key(identifier):
    """Perform the EVE API call to validate the given identifier, and update relevant details."""
    
    from brave.core.util.eve import APICall
    from brave.core.key.model import EVECredential
    
    cred = EVECredential.objects.get(id=identifier)
    
    try:
        result = APICall.objects.get(name='account.APIKeyInfo')(cred)
    except HTTPError as e:
        if e.response.status_code == 403:
            # the key has been disabled; remove it
            cred.delete()
            return
        else:
            raise
    
    cred.mask = int(result['accessMask'])
    cred.kind = result['type']
    cred.expires = datetime.strptime(result['expires'], '%Y-%m-%d %H:%M:%S') if result.get('expires', None) else None
    cred.verified = cred.mask != 0
    cred.save()
    
    cred.pull()


@signal(post_save)
def trigger_api_validation(sender, document, **kwargs):
    """Trigger validation of newly created EVE API Credential documents."""
    
    if not kwargs.get('created', False):
        return
    
    if config.get('debug', False):
        validate_key(document.id)
    
    else:
        validator_pool.submit(validate_key, document.id)
