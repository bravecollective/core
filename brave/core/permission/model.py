# encoding: utf-8

from __future__ import unicode_literals

from mongoengine import Document, StringField


log = __import__('logging').getLogger(__name__)

GRANT_WILDCARD = '*'


def create_permission(permission, description=None):
    """This function creates and returns a permission object of the correct class (Permission vs. WildcardPermission).
    As such, it is useful for creating a permission where you do not know at compile-time whether it is a Permission
    or WildcardPermission. In the event of id conflicts (the permission already exists), this function returns False."""
    
    if Permission.objects(id=permission):
        log.debug("Permission with id {0} already exists.".format(permission))
        return False
    
    if GRANT_WILDCARD in permission:
        perm = WildcardPermission(permission, description)
    else:
        perm = Permission(permission, description)
        
    return perm.save()


class Permission(Document):
    meta = dict(
        collection='Permissions',
        allow_inheritance=True,
        indexes=[
            dict(fields=['id'])
        ],
    )
    
    id = StringField(primary_key=True)
    description = StringField(db_field='d')
    
    # Permissions
    GRANT_PERM = 'core.permission.grant.{permission_id}'
    REVOKE_PERM = 'core.permission.revoke.{permission_id}'
    
    @property
    def application(self):
        """Returns the application that this permission is for."""
        
        from brave.core.application.model import Application
        
        # Handle '*' properly
        if self.id.find('.') == -1:
            return None
        
        app_short = self.id.split('.')[0]
        
        app = Application.objects(short=app_short)
        
        if not len(app):
            return None
        else:
            return app.first()
            
    def __repr__(self):
        return "Permission('{0}')".format(self.id)
            
    def get_permissions(self):
        """Returns all permissions granted by this Permission."""
        
        return set({self})
        
    def grants_permission(self, perm_string):
        """This is used to see if a Permission grants access to a permission which is not in the database.
            For instance, when evaluating whether a WildcardPermission grants access to a run-time permission."""
        
        return(self.id == perm_string)
    
    @staticmethod
    def set_grants_permission(perms, permission):
        """Loops through a set of permissions and checks if any of them grants the desired permission."""
        
        return any(p.grants_permission(permission) for p in perms)
    
    def __eq__(self, other):
        if isinstance(other, Permission):
            return self.id == other.id
        return False
        
    def __ne__(self, other):
        return not self.__eq__(other)
        
    def get_perm(self, perm_type):
        return getattr(self, perm_type+"_PERM").format(permission_id=self.id)
        
    @property
    def grant_perm(self):
        return self.get_perm('GRANT')
        
    @property
    def revoke_perm(self):
        return self.get_perm('REVOKE')
        
class WildcardPermission(Permission):
    
    def __repr__(self):
        return "WildcardPermission('{0}')".format(self.id)
            
    def get_permissions(self):
        """Returns all Permissions granted by this Permission"""
        
        from brave.core.application.model import Application
        
        # Mongoengine has no way to find objects based on a regex (as far as I can tell at least...)
        perms = set()

        # Loops through all of the permissions, checking if this permission grants access to that permission.
        for perm in Permission.objects():
            if self.grants_permission(perm.id):
                perms.add(perm)
        
        return perms
        
    def grants_permission(self, perm_string):
        """This is used to see if a Permission grants access to a permission which is not in the database.
            For instance, when evaluating whether a WildcardPermission grants access to a run-time permission."""
        # Splits both this permission's id and the permission being checked.
        self_segments = self.id.split('.')
        perm_segments = perm_string.split('.')
        
        # If this permission has more segments than the permission we're matching against, it can't provide access
        # to that permission.
        if len(self_segments) > len(perm_segments):
            return False
        
        # If the permission we're checking against is longer than the wildcard permission (this permission), then this
        # permission must end in a wildcard for it to grant the checked permission.
        if len(self_segments) < len(perm_segments):
            if GRANT_WILDCARD != self_segments[-1]:
                return False
        
        # Loops through each segment of the wildcardPerm and permission id. 'core.example.*.test.*' would have
        # segments of 'core', 'example', '*', 'test', and '*' in that order.
        for (s_seg, perm_seg) in zip(self_segments, perm_segments):
            # We loop through looking for something wrong, if there's nothing wrong then we return True.
            
            # This index is a wildcard, so we skip checks
            if s_seg == GRANT_WILDCARD:
                continue
            
            # If this self segment doesn't match the corresponding segment in the permission, this permission
            # doesn't match, and we return False
            if s_seg != perm_seg:
                return False
        
        return True
