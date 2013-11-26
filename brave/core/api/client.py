# encoding: utf-8

from __future__ import unicode_literals, print_function

from webob import Response
from marrow.util.url import URL
from marrow.util.bunch import Bunch
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


class API(object):
    __slots__ = ('endpoint', 'identity', 'private', 'public')
    
    def __init__(self, endpoint, identity, private, public):
        self.endpoint = URL(endpoint)
        self.identity = identity
        self.private = private
        self.public = public
    
    def __getattr__(self, name):
        return API(
                "{0}/{1}".format(self.endpoint, name),
                self.identity,
                self.private,
                self.public
            )
    
    def __call__(self, *args, **kwargs):
        result = requests.post(
                URL("{0}/{1}".format(self.endpoint, '/'.join(args))).render(),
                data = kwargs,
                auth = SignedAuth(self.identity, self.private, self.public)
            )
        
        if not result.status_code == requests.codes.ok:
            return None
        
        return Bunch(result.json())


# Test function has been moved to brave.core.controller:DeveloperTools.authn
# Web-accessible: http://localhost:8080/dev/authn
