from brave.core.permission.model import Permission, WildcardPermission, GRANT_WILDCARD


def createPerms(permString, app=None):
    perms = permString.split("\n")
    
    for p in perms:
        # Ignore blank lines
        if not p:
            continue
        perm = p.split(":", 1)[0]
        desc = p.split(":", 1)[1]
        
        # Check if the permission is for the app provided, if not, stop executing and die
        if app:
            permApp = perm.split('.')[0]
            if permApp != app:
                return False
        
        p = Permission.objects(id=perm)
        if len(p):
            p = p.first()
            p.desc = desc
            p.save()
            continue
        
        if GRANT_WILDCARD in perm:
            permission = WildcardPermission(perm, desc)
        else:
            permission = Permission(perm, desc)
            
        permission.save()
    return True


def init_perms():
    f = open('permissions.txt', 'r')
    permString = ""
    for line in f:
        permString += line + "\n"
    
    createPerms(permString)
