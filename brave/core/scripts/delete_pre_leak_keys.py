from brave.core.key.model import EVECredential

def delete(delete=False):
    """ Deletes every key from before the leak from the database."""
    
    x = 0
    
    for c in EVECredential.objects(key__lt=3283828):
        x += 1
        print c.key
        if delete:
            c.delete()

    print "Deleted {0} keys.".format(x)
