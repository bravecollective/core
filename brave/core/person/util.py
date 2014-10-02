
from brave.core.character.model import EVECharacter
from brave.core.key.model import EVECredential
from brave.core.account.model import User

def object_repr(object):
    """Returns the primary identification of the component."""

    from brave.core.person.model import Person

    if isinstance(object, EVECharacter):
        return object.name
    elif isinstance(object, User):
        return object.username
    elif isinstance(object, EVECredential):
        return str(object.key)
    elif isinstance(object, basestring):
        return object
    elif isinstance(object, Person):
        return str(object.id)
    else:
        return None


def get_type(object):

    from brave.core.person.model import Person

    if isinstance(object, basestring):
        return "ip"
    elif isinstance(object, EVECharacter):
        return "character"
    elif isinstance(object, EVECredential):
        return "key"
    elif isinstance(object, User):
        return "user"
    elif isinstance(object, Person):
        return "person"
