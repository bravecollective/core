
from brave.core.character.model import EVECharacter
from brave.core.key.model import EVECredential
from brave.core.account.model import User
from brave.core.person.model import Person

def object_repr(object):
    """Returns the primary identification of the component."""
    type = type(object)
    if type == EVECharacter:
        return object.name
    elif type == User:
        return object.username
    elif type == EVECredential:
        return object.key
    elif type == str or type == unicode:
        return object
    elif type == Person:
        return object.id
    else:
        return None


def get_type(object):
    type = type(object)

    if type == str or type == unicode:
        type = "ip"
    elif type == EVECharacter:
        type = "character"
    elif type == EVECredential:
        type = "key"
    elif type == User:
        type = "user"
    elif type == Person:
        type = "person"
