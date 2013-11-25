# encoding: utf-8

from __future__ import unicode_literals

from binascii import hexlify, unhexlify
from hashlib import sha256

from ecdsa.keys import SigningKey, VerifyingKey
from ecdsa.curves import NIST256p

from brave.core.util.signal import signal, post_save, validator_pool

log = __import__('logging').getLogger(__name__)


def generate_key(identifier):
    from brave.core.application.model import Application
    
    key = SigningKey.generate(NIST256p, hashfunc=sha256)
    Application.objects(id=identifier, key__private=None).update(set__key__private=hexlify(key.to_string()))


def log_error(receipt):
    try:
        receipt.result()
    except:
        log.exception("Error during private key generation.")


@signal(post_save)
def trigger_private_key_generation(sender, document, **kwargs):
    """Trigger creation of a new application-specific private key."""
    
    if not kwargs.get('created', False):
        return
    
    if config.get('debug', False):
        generate_key(document.id)
    
    else:
        receipt = validator_pool.submit(generate_key, document.id)
        receipt.add_done_callback(log_error)
