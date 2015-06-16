# encoding: utf-8

from __future__ import unicode_literals

from brave.core.permission.model import WildcardPermission
from web.core.http import HTTPForbidden
from brave.core.util.predicate import authenticate
import web.auth

log = __import__('logging').getLogger(__name__)


def prepare_runtime_permission(self, perm=None, runkw=None, args=None, kwargs=None):
    """This decorator handles the runtime permission aspects of the user permission checking decorators."""
    permission = perm

    if not permission:
        log.debug('No permission provided.')
        return False

    for key, value in runkw.iteritems():
        valSplit = value.split('.')
        for attr in valSplit:
            if attr == "self":
                value = self
                continue
            elif attr in kwargs:
                value = kwargs.get(attr)
                continue
            value = getattr(value, attr)

        permission = permission.replace('{' + key + '}', value)

    return permission


def user_has_permission(perm=None, **runkw):
    """This decorator checks if a user has the permission 'perm'. This is intended as a convenient way to check for
    a user's ability to conduct an action at the beginning of functions, such as for HTTP GET and POST requests. If a
    user does not have the permission sepcified, the decorator raises a 403 error. **runkw is used to allow for
    checking permissions which are not known at compile time, such as when they rely on arguments supplied to the
    decorated function. To use **runkw, set up perm as if you were formatting it using kw arguments, and then supply
    those kw arguments to the decorator as a string."""

    def decorator(function):

        @authenticate
        def check_permission(self, *args, **kwargs):
            user = web.auth.user

            user = user._current_obj()

            permission = prepare_runtime_permission(self, perm, runkw, args, kwargs)

            # No permission provided, so everyone has permission.
            if not permission:
                return function(self, *args, **kwargs)

            # No user with that username was found.
            if not user:
                log.debug('User not found.')
                raise HTTPForbidden()

            # User has no characters, so they have no permissions.
            if not len(user.characters):
                log.debug('User has no characters.')
                raise HTTPForbidden()

            # Cycle through the user's permissions, and if they have it leave the method.
            if user.primary.has_permission(permission):
                return function(self, *args, **kwargs)

            # Cycle through the user's permissions, and if they have it leave the method.
            for c in user.characters:
                if c.has_permission(permission):
                    return function(self, *args, **kwargs)

            # User doesn't have this permission, so we raise HTTPForbidden
            log.debug('User has no characters with that permission.')
            raise HTTPForbidden()

        return check_permission

    return decorator


def user_has_any_permission(perm=None, **runkw):
    """This decorator checks if the user has any permission granted my perm. See user_has_permission for more details
    such as how to use **runkw."""

    def decorator(function):

        @authenticate
        def check_permission(self, *args, **kwargs):
            user = web.auth.user

            user = user._current_obj()

            permission = prepare_runtime_permission(self, perm, runkw, args, kwargs)

            # No permission provided, so everyone has permission.
            if not permission:
                return function(self, *args, **kwargs)

            # No user with that username was found.
            if not user:
                log.debug('User not found.')
                raise HTTPForbidden()

            # User has no characters, so they have no permissions.
            if not len(user.characters):
                log.debug('User has no characters.')
                raise HTTPForbidden()

            p = WildcardPermission.objects(id=permission).first()
            if not p:
                p = WildcardPermission(id=permission)
            for permID in user.permissions:
                if p.grants_permission(permID.id):
                    return function(self, *args, **kwargs)
                if permID.grants_permission(p.id):
                    return function(self, *args, **kwargs)

            # User doesn't have this permission, so we raise HTTPForbidden
            log.debug('User has no characters with that permission.')
            raise HTTPForbidden()

        return check_permission

    return decorator
