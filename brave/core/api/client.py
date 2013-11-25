# encoding: utf-8

from __future__ import unicode_literals, print_function

from webob import Response
from datetime import datetime
from binascii import hexlify, unhexlify
from hashlib import sha256
from ecdsa.keys import SigningKey, VerifyingKey
from ecdsa.curves import NIST256p

import requests
from requests.auth import AuthBase


log = __import__('logging').getLogger(__name__)


class SignedAuth(AuthBase):
    def __init__(self, identity, private, public):
        self.identity = identity
        self.private = private
        self.public = public
    
    def __call__(self, request):
        log.info("Signing request to: %s", request.url)
        request.headers['Date'] = Response(date=datetime.utcnow()).headers['Date']
        request.headers['X-Service'] = self.identity
        canon = "{r.headers[date]}\n{r.url}\n{r.body}".format(r=request)
        request.headers['X-Signature'] = hexlify(self.private.sign(canon))
        
        log.debug("Signature: %s", request.headers['X-Signature'])
        log.debug("Canonical data:\n%r", canon)
        
        request.register_hook('response', self.validate)
        
        return request
    
    def validate(self, response, *args, **kw):
        if response.status_code != requests.codes.ok:
            log.debug("Skipping validation of non-200 response.")
            return
        
        log.info("Validating %s request signature: %s", self.identity, response.headers['X-Signature'])
        canon = "{ident}\n{r.headers[Date]}\n{r.url}\n{r.content}".format(ident=self.identity, r=response)
        log.debug("Canonical data:\n%r", canon)
        
        # Raises an exception on failure.
        self.public.verify(unhexlify(response.headers['X-Signature']), canon)


def test():
    # echo "from brave.core.api.client import test; print(test().text)" | paster shell
    
    import calendar
    from datetime import datetime
    
    identity = '5292f5de6f692bf7e20f9e57'
    private = SigningKey.from_string(unhexlify('fe3dc8bfb1745fb8a697fed5d6680143e9f22acac6bf3031c31ee737ff50e501'), curve=NIST256p, hashfunc=sha256)
    public = private.get_verifying_key()
    
    
    auth = SignedAuth(identity, private, public)
    
    
    resp = requests.post(
            'http://localhost:8080/api/ping',
            data = dict(now=calendar.timegm(datetime.utcnow().utctimetuple())),
            auth = auth
        )
    
    return resp
