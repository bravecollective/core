from brave.core.group.model import Group
from brave.core.permission.model import Permission

def findPermissionInGroups(needle):
    print("Searching for " + needle)
    gs = Group.objects()
    for g in gs:
        for p in g._permissions:
            if needle in p.id:
                #print ("{0}".format(p.id))
                print ("{0} has {1}".format(g.id, p.id))

findPermissionInGroups('cap')
