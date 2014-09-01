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
from web.core import request, session
from web.core.templating import render
from web.core.locale import _

from brave.core.account.model import User, LoginHistory, PasswordRecovery, YubicoOTP

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


def verify_credentials(identifier, password):
    """Given an e-mail address (or Yubikey OTP) and password, authenticate a user and return the User object. This does
    not set up the user in WebCore; to do that you must call authenticate."""
    
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
    
    if not user or not User.password.check(user.password, password) or (user.otp_required and not 'otp' in query and 
        isinstance(user.otp, YubicoOTP)):
        if user:
            LoginHistory(user, False, request.remote_addr).save()
        
        # Prevent basic timing attacks; always take at least one second to process.
        sleep(max(min(1 - (time() - ts), 0), 1))
        
        return None
    
    # Validate Yubikey OTP
    if 'otp' in query:
        if not user.otp or not user.otp.validate(identifier):
            return None
            
    session['auth'] = datetime.now()
    session['preauth_username'] = user.username
    session.save()
    
    return user


# @authentication_logger
def authenticate(user, *args, **kwargs):
    """This function does not do any verification of identitiy, that MUST be done prior to calling this. What it does
    do is set up the user object in WebCore for use else where."""
    
    user.update(set__seen=datetime.utcnow())
    
    # Record the fact the user signed in.
    LoginHistory(user, True, request.remote_addr).save()
    
    # Update the user's host
    user.host = request.remote_addr
    
    # Check for other accounts with this IP address
    if len(User.objects(host=request.remote_addr)) > 1:
        # Quite possibly the worst code ever
        for u in User.objects(host=request.remote_addr):
                User.add_duplicate(user, u, IP=True)

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
