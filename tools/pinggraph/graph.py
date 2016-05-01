from brave.core.group.model import Group
from brave.core.permission.model import Permission

def graph(name):
    print ('Graphing: ' + name)
    f = open(name + 'dot','w')
    f.write("digraph P {\n")
    f.write("overlap=false\n")
    gs = Group.objects()
    for g in gs:
        if not name in g.id:
            continue
        f.write("\"{0}\" [shape=box];\n".format(g.id))
        for p in g._permissions:
            if not "jabber.ping." in p.id:
                continue
            if ".receive." in p.id:
                f.write("\"{0}\" -> \"{1}\" [color=green];\n".format(p.id.replace("jabber.ping.receive.",""), g.id))
            if ".send." in p.id:
                f.write("\"{0}\" -> \"{1}\" [color=red];\n".format(g.id, p.id.replace("jabber.ping.send.","")))
    f.write("}\n")
    f.close()

print("Running")
graph('alliance.edu.')


