from brave.core.application.model import ApplicationGrant

def migrate_characters(dry_run=True):
    """Migrate from single-character application grants to multi-character ones
    """

    count = 0
    for grant in ApplicationGrant.objects(character__ne=None):
        print '{g.application.name} - {g.character.name}'.format(g=grant)
        count += 1
        if not dry_run:
            grant.chars = [grant.character]
            grant.character = None
            grant.save()

    print 'Updated {} grants'.format(count)
