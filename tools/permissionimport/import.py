from brave.core.group.model import Group
from brave.core.permission.model import Permission,WildcardPermission

dryrun = True

def massimport(name):
    print ('Importing group: ' + name)
    if dryrun:
        print ("*** DRYRUN, nothing is changed!")
    g = Group.objects(id=name).first()
    with open(name + '.txt', 'rb') as fd:
        temp = fd.read().splitlines()
        for line in temp:
            print ("  Applying: " + line)
            p = Permission.objects(id=line)
            if len(p):
                p = p.first()
                print ("    Permission existed: {0}".format(p.id))
            else:
                if '*' in line:
                    p = WildcardPermission(line)
                else:
                    p = Permission(line)
                print ("    Permission created: {0}".format(p.id))
                if not dryrun:
                    p.save()
            g._permissions.append(p)
            print ("    Group updated: {0} - {1}".format(g.id, g._permissions))
            if not dryrun:
                g.save()

print("Running")
massimport('this.is.my.group')
