# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime

from web.core import Controller
from mongoengine.signals import pre_save, post_save
from marrow.util.futures import ScalingPoolExecutor
from marrow.util.bunch import Bunch
from marrow.mailer import Mailer
from web.core import config

from brave.core import util

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

@signal(post_save)
def trigger_api_validation(sender, document, **kwargs):
    """Trigger validation of newly created EVE API Credential documents."""
    from brave.core.key.model import EVECredential
    
    if not kwargs.get('created', False):
        return
    
    if config.get('debug', False):
        EVECredential.objects(id=document.id).first().pull()
    
    else:
        validator_pool.submit(EVECredential.object(id=document.id).first().pull)
