# encoding: utf-8

from web.auth import authorize
from web.auth import CustomPredicate, Not, All, Any, anonymous, authenticated, AttrIn, ValueIn, EnvironIn
import web.auth
from web.core.http import HTTPUnauthorized

# Administrators are explicit.
is_administrator = AttrIn('admin', [True, ])

# Local users for development-only methods.
is_local = EnvironIn('REMOTE_ADDR', ('127.0.0.1', '::1', 'fe80::1%%lo0'))


log = __import__('logging').getLogger(__name__)

def authenticate(function):
    
    def loggedIn(self, *args, **kwargs):
        user = web.auth.user
        
        # If there is no StackedObjectProxy or User object for this user, then they're not logged in.
        if not user or not user._current_obj():
            log.debug('user not a valid object')
            raise HTTPUnauthorized()

        if user.person.banned():
            log.debug("User is global banned")
            web.auth.deauthenticate()
            raise HTTPUnauthorized()
        
        return function(self, *args, **kwargs)
            
    return loggedIn
