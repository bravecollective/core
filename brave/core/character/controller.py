# encoding: utf-8

from web.auth import user
from web.core import Controller, HTTPMethod, request
from web.core.locale import _
from web.core.http import HTTPFound, HTTPNotFound
from marrow.util.bunch import Bunch

from brave.core.character.model import EVECharacter
from brave.core.util.predicate import authorize, authenticated, is_administrator


class CharacterInterface(HTTPMethod):
    def __init__(self, char):
        super(CharacterInterface, self).__init__()

        try:
            self.char = EVECharacter.objects.get(id=char)
        except EVECharacter.DoesNotExist:
            raise HTTPNotFound()

        if self.char.owner.id != user.id and not user.admin:
            raise HTTPNotFound()

    @authorize(authenticated)
    def put(self):
        if self.char.owner.id != user.id:
            raise HTTPNotFound()
        
        u = user._current_obj()
        u.primary = self.char
        u.save()

        if request.is_xhr:
            return 'json:', dict(success=True)

        raise HTTPFound(location='/character/')
        
    @authorize(authenticated)
    def get(self):
        if self.char.owner.id != user.id and not user.admin:
            raise HTTPNotFound()
        
        return 'brave.core.character.template.charDetails', dict(
            char=self.char,
            area='admin'
        )

class CharacterList(HTTPMethod):
    @authorize(authenticated)
    def get(self, admin=False):
        if admin and not is_administrator:
            raise HTTPNotFound()
            
        characters = user.characters
        if admin:
            characters = EVECharacter.objects()

        return 'brave.core.character.template.list', dict(
                area='chars',
                admin=bool(admin),
                records=characters
            )


class CharacterController(Controller):
    """Entry point for the KEY management RESTful interface."""

    index = CharacterList()

    def __lookup__(self, char, *args, **kw):
        request.path_info_pop()  # We consume a single path element.
        return CharacterInterface(char), args
