from brave.core.key.model import EVECredential

def delete():
    """ Deletes every duplicate key in the database."""
    """ WARNING: DELETED EVERY INSTANCE OF THAT KEY."""
    dups = []
    
    for credential in EVECredential.objects():
        if len(EVECredential.objects(key=credential.key)) > 1:
            for c in EVECredential.objects(key=credential.key):
                dups.append(c)

    print "Deleting {0} keys.".format(len(set(dups)),)

    for c in dups:
        c.delete()
