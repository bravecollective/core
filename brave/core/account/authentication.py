# encoding: utf-8

"""WebCore authentication and session restoration callbacks.

These implement our particular flavour of authentication: a loose identity based on user name, e-mail address, or
Yubikey OTP token and (regardless of identifier) a password.  Actual password crypto happens in:

    brave.core.util.field:PasswordField.check
"""

from __future__ import unicode_literals

from random import SystemRandom
from time import time, sleep
from datetime import datetime
from yubico import yubico
from marrow.util.convert import boolean
from web.core import config, request
from web.core.templating import render
from web.core.locale import _

from brave.core.account.model import User, LoginHistory, PasswordRecovery

import brave.core.util as util

log = __import__('logging').getLogger(__name__)



def lookup(identifier):
    """Thaw current user data based on session-stored user ID."""

    user = User.objects(id=identifier).first()
    
    if user:
        user.update(set__seen=datetime.utcnow())  # , set__host=request.remote_addr -- chicken-egg problem

    return user


def lookup_email(email):
    """get user by email address"""
    user = User.objects(email=email).first()
    return user

def authentication_logger(fn):
    """Decorate the authentication handler to log attempts.
    
    Log format:
    
    AUTHN {status} {ip} {uid or identifier}
    """
    def inner(identifier, password):
        result = fn(identifier, password)
        
        if result:
            record, user = result
            log.info("AUTHN PASS %s %s", request.remote_addr, record)
            return result
        
        log.info("AUTHN FAIL %s %s", request.remote_addr, identifier)
        return result


# @authentication_logger
def authenticate(identifier, password):
    """Given an e-mail address (or Yubikey OTP) and password, authenticate a user."""
    
    ts = time()  # Record the 
    query = dict(active=True)
    
    # Gracefully handle extended characters in passwords.
    # The password storage algorithm works in binary.
    if isinstance(password, unicode):
        password = password.encode('utf8')
    
    # Build the MongoEngine query to find 
    if '@' in identifier:
        query[b'email'] = identifier
    elif len(identifier) == 44:
        query[b'otp'] = identifier[:12]
    else:
        query[b'username'] = identifier
    
    user = User.objects(**query).first()
    
    if not user or not User.password.check(user.password, password) or (user.otp_required and not 'otp' in query):
        if user:
            LoginHistory(user, False, request.remote_addr).save()
        
        # Prevent basic timing attacks; always take at least one second to process.
        sleep(max(min(1 - (time() - ts), 0), 1))
        
        return None
    
    # Validate Yubikey OTP
    if 'otp' in query:
        client = yubico.Yubico(
                config['yubico.client'],
                config['yubico.key'],
                boolean(config.get('yubico.secure', False))
            )
        
        try:
            status = client.verify(identifier, return_response=True)
        except:
            return None
        
        if not status:
            return None
    
    user.update(set__seen=datetime.utcnow())
    
    # Record the fact the user signed in.
    LoginHistory(user, True, request.remote_addr).save()
    
    # Update the user's host
    user.host = request.remote_addr
    
    user.person.add_component((user, "user_add"), request.remote_addr)

    user.save()
    
    return user.id, user


def send_recover_email(user):
    """Sends a recovery-link to the specified user objects' email address"""
    # generate recovery key
    recovery_key = SystemRandom().randint(0, (2<< 62)-1)

    # send email
    params = {'email': user.email, 'recovery_key': str(recovery_key)}
    mailer = util.mail
    message = mailer.new(to=user.email, subject=_("Password Recovery - Brave Collective Core Services"))

    #explicitley get the text contend for the mail
    mime, content = render("brave.core.account.template.mail/lost.txt", dict(params=params))
    message.plain = content

    #explicitley get the html contend for the mail
    mime, content = render("brave.core.account.template.mail/lost.html", dict(params=params))
    message.rich = content

    mailer.send(message)

    # store key in DB
    PasswordRecovery(user, recovery_key).save()
