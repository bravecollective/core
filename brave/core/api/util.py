# encoding: utf-8

from __future__ import unicode_literals

from datetime import datetime
from binascii import hexlify, unhexlify
from hashlib import sha256
from ecdsa.keys import SigningKey, VerifyingKey
from ecdsa.curves import NIST256p

from webob import Response
from web.core.http import HTTPBadRequest
from web.core import request, Controller, HTTPMethod
from web.core.templating import render

from brave.core.application.model import Application


log = __import__('logging').getLogger(__name__)



class SignedController(Controller):
    def __before__(self, *args, **kw):
        """Validate the request signature, load the relevant data."""
        
        if 'X-Service' not in request.headers or 'X-Signature' not in request.headers:
            log.error("Digitally signed request missing headers.")
            raise HTTPBadRequest("Missing headers.")
        
        try:
            request.service = Application.objects.get(id=request.headers['X-Service'])
        except Application.DoesNotExist:
            raise HTTPBadRequest("Unknown service identity.")
        
        key = VerifyingKey.from_string(unhexlify(request.service.key.public), curve=NIST256p, hashfunc=sha256)
        
        log.debug("Canonical request:\n\n\"{r.headers[Date]}\n{r.url}\n{r.body}\"".format(r=request))
        if not key.verify(unhexlify(request.headers['X-Signature']), "{r.headers[Date]}\n{r.url}\n{r.body}".format(r=request)):
            raise HTTPBadRequest("Invalid request signature.")
        
        return args, kw
    
    def __after__(self, result, *args, **kw):
        """Generate the JSON response and sign."""
        
        key = SigningKey.from_string(unhexlify(request.service.key.private), curve=NIST256p, hashfunc=sha256)
        
        response = Response(status=200, charset='utf-8')
        response.date = datetime.utcnow()
        response.last_modified = result.pop('updated', None)
        
        ct, body = render('json:', result)
        response.headers[b'Content-Type'] = str(ct)  # protect against lack of conversion in Flup
        response.body = body
        
        canon = "{req.service.id}\n{resp.headers[Date]}\n{req.url}\n{resp.body}".format(
                    req = request,
                    resp = response
            )
        response.headers['X-Signature'] = hexlify(key.sign(canon))
        log.debug("Signing response: %s", response.headers['X-Signature'])
        log.debug("Canonical data:\n%r", canon)
        
        del response.date
        
        return response
