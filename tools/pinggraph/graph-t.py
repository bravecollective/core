from brave.core.group.model import Group
from brave.core.permission.model import Permission

def graph(name, pings):
    print ('Graphing: ' + name)
    f = open(name + '.dot','w')
    f.write("digraph P {\n")
    f.write("overlap=false\n")
    gs = Group.objects()
    groups = []
    for g in gs:
        for p in g._permissions:
            if not p.id.startswith("ping."):
                continue
            pname = p.id.replace("ping.send.","").replace("ping.receive.","")
            if pname in pings:
                if not g.id in groups:
                    groups.append(g.id)
                if ".receive." in p.id:
                    f.write("\"{0}\" -> \"{1}\" [color=green];\n".format(pname, g.id))
                if ".send." in p.id:
                    f.write("\"{1}\" -> \"{0}\" [color=red];\n".format(pname, g.id))
    for g in groups:
        f.write("\"{0}\" [shape=box];\n".format(g))
    f.write("}\n")
    f.close()

print("Running")
graph('dojo', ['dojo', 'dojodir', 'dojostaff'])
