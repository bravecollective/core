from __future__ import absolute_import, print_function, unicode_literals

import sys
from brave.core import core_loadapp
from brave.core.person.model import Person, PersonEvent

if __name__ == "__main__":
    core_loadapp("config:"+sys.argv[1] if len(sys.argv) > 1 else None)

def generate_people(dry_run=True, wipe_db=False):
    """Note: it is highly recommended that you only use this method on an empty People collection
    Also note, this is untested for large and complex Person and PersonEVent collections, so use at your own risk."""

    persons_modified = 0
    events_processed = 0

    if wipe_db:
        people_deleted = 0
        print("Deleting People collection prior to regeneration.")
        for p in Person.objects:
            people_deleted += 1

            if dry_run:
                continue

            p.delete()
        print("Deleted {0} people".format(people_deleted))

    for e in PersonEvent.objects.order_by("time"):
        events_processed += 1
        p = Person.objects(id=e.person).first()
        if not p:
            persons_modified += 1

            if dry_run:
                continue

            p = Person(id=e.person)
            p = p.save()

        if dry_run:
            continue

        if e.action == "add":
            p.add_component((e.match, e.reason), e.target, suppress_events=True)
        elif e.action == "remove":
            p.remove_component((e.match, e.reason), e.target, suppress_events=True)
        elif e.action == "merge":
            Person.merge(p, e.target, (e.match, e.reason), suppress_events=True)

    print("Regenerated Person collection: {0} Persons modified, {1} Events processed.".format(persons_modified, events_processed))
