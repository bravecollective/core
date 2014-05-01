# encoding: utf-8

from __future__ import unicode_literals

from web.auth import user
from web.core import Controller, HTTPMethod, request, config
from web.core.locale import _
from web.core.http import HTTPFound, HTTPNotFound, HTTPUnauthorized
from web.core.templating import render
from marrow.util.convert import boolean
from marrow.util.bunch import Bunch
from mongoengine import ValidationError

from brave.core.key.model import EVECredential
from brave.core.util.predicate import authorize, authenticated, is_administrator


log = __import__('logging').getLogger(__name__)

KEY_RESET_FLOOR = 3283828


class KeyIndex(HTTPMethod):
    def __init__(self, key):
        super(KeyIndex, self).__init__()
        self.key = key

    def delete(self):
        owner = self.key.owner
        
        #Delete the key
        self.key.delete()
        
        #Delete any character that the key owner has registered, but no longer has a key for.
        for c in owner.characters:
            if not c.credential_for(0):
                c.delete()

        if request.is_xhr:
            return 'json:', dict(success=True)

        raise HTTPFound(location='/key/')


class KeyInterface(Controller):
    def __init__(self, key):
        super(KeyInterface, self).__init__()
        
        try:
            self.key = EVECredential.objects.get(id=key)
        except EVECredential.DoesNotExist:
            raise HTTPNotFound()

        if self.key.owner.id != user.id:
            raise HTTPNotFound()
        
        self.index = KeyIndex(self.key)
    
    def refresh(self):
        try:
            self.key.pull()
        except:
            log.exception("Unable to reload key.")
            
            if boolean(config.get('debug', False)):
                raise
            
            return 'json:', dict(success=False)
        
        return 'json:', dict(success=True)


class KeyList(HTTPMethod):
    @authorize(authenticated)
    def get(self, admin=False):
        admin = boolean(admin)
        
        if admin and not is_administrator:
            raise HTTPNotFound()

        return 'brave.core.key.template.list', dict(
                area = 'keys',
                admin = admin,
                records = user.credentials
            )

    @authorize(authenticated)
    def post(self, **kw):
        data = Bunch(kw)
        
        try:
            data.key = int(data.key)
            if data.key <= KEY_RESET_FLOOR:
                return 'json:', dict(success=False, 
                                     message=_("The key given (%d) must be above minimum reset floor value of %d. Please reset your EVE API Key." % (data.key, KEY_RESET_FLOOR)), 
                                     field='key')
                
        except ValueError:
            return 'json:', dict(success=False, message=_("Key ID must be a number."), field='key')
        
        record = EVECredential(data.key, data.code, owner=user.id)
        
        try:
            record.save()
            record.pull()
            characters = []
            for character in record.characters:
                characters.append(dict(identifier = character.identifier, name = character.name))

            if request.is_xhr:
                return 'json:', dict(
                        success = True,
                        message = _("Successfully added EVE API key."),
                        identifier = str(record.id),
                        key = record.key,
                        code = record.code,
                        characters = characters
                    )
        
        except ValidationError:
            if request.is_xhr:
                return 'json:', dict(
                        success = False,
                        message = _("Validation error: one or more fields are incorrect or missing."),
                    )

        raise HTTPFound(location='/key/')


class KeyController(Controller):
    """Entry point for the KEY management RESTful interface."""

    index = KeyList()
    
    def add(self):
        # TODO: mpAjax mime/multipart this to save on escaping the HTML.
        # https://github.com/getify/mpAjax
        return 'json:', dict(
                title = _("Add New API Key"),
                content = render('mako:brave.core.key.template.add', dict()),
                label = dict(label=_("Add Key"), kind='btn-success')
            )
    
    def __lookup__(self, key, *args, **kw):
        request.path_info_pop()  # We consume a single path element.
        return KeyInterface(key), args
