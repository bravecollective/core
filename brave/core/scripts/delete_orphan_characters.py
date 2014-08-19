from brave.core.character.model import EVECharacter
from brave.core.util.eve import EVECharacterKeyMask

def delete(override = False):
    """ Deletes every orphaned character in the database."""
    """ WARNING: BACK UP YOUR DATABASE BEFORE RUNNING."""
    dels = 0
    errors = 0
    
    for character in EVECharacter.objects():
        try:
            if not character.credential_for(EVECharacterKeyMask.NULL):
                character.delete()
                dels += 1
        except AttributeError:
            # There's a problem with the character (messed up references perhaps)
            # So delete anyways.
            if override:
                character.delete()
                dels += 1
            else:
                print "Error with character {0}.".format(character,)
                errors += 1

    print "Deleted {0} characters.".format(dels,)
    if errors:
        print "Encountered {0} errors, resolve these manually or run delete True as its argument.".format(errors,)
