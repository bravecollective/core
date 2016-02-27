from brave.core.group.model import Group
from brave.core.permission.model import Permission

def removePermissionInGroups(needle):
    print("Searching for " + needle)
    gs = Group.objects()
    for g in gs:
	touched = False
        for p in g._permissions:
            if p.id.startswith(needle):
                #print ("{0}".format(p.id))
                print ("{0} has {1}".format(g.id, p.id))
                g._permissions.remove(p)
		touched = True
	if touched:
	    g.save()

removePermissionInGroups('example.permission.a')
