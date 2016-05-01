from brave.core.group.model import Group
from brave.core.permission.model import Permission
from brave.core.ban.model import Ban, PersonBan

def findPermissionInGroups(needle):
    print("Searching for " + needle)
    bs = Ban.objects()
    for b in bs:
	if b.ban_type != 'service' and b.expires is None:
	    print("{3} has been {0} for {1} because {2}".format(b.ban_type, b.expires, b.reason, b.banned_ident))

findPermissionInGroups('core.ban')

