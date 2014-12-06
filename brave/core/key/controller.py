# encoding: utf-8

from __future__ import unicode_literals

from web.auth import user
from web.core import Controller, HTTPMethod, request, config
from web.core.locale import _
from web.core.http import HTTPFound, HTTPNotFound, HTTPForbidden
from web.core.templating import render
from marrow.util.convert import boolean
from marrow.util.bunch import Bunch
from mongoengine import ValidationError
from mongoengine.errors import NotUniqueError

from brave.core.account.model import User
from brave.core.key.model import EVECredential
from brave.core.util.predicate import authenticate
from brave.core.util.eve import EVECharacterKeyMask, EVECorporationKeyMask


log = __import__('logging').getLogger(__name__)


class KeyIndex(HTTPMethod):
    def __init__(self, key):
        super(KeyIndex, self).__init__()
        self.key = key

    def delete(self):
        owner = self.key.owner
        
        #Delete the key
        self.key.delete()

        if request.is_xhr:
            return 'json:', dict(success=True)

        raise HTTPFound(location='/key/')
        
    def get(self):
        return 'brave.core.key.template.keyDetails', dict(
            area='admin' if user.admin else 'keys',
            admin=True,
            record=self.key
        )


class KeyInterface(Controller):
    
    @authenticate
    def __init__(self, key):
        super(KeyInterface, self).__init__()
        
        try:
            self.key = EVECredential.objects.get(id=key)
        except EVECredential.DoesNotExist:
            raise HTTPNotFound()

        if self.key.owner.id != user.id and not user.has_permission(self.key.view_perm):
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
    @authenticate
    def get(self, admin=False):
        admin = boolean(admin)
        
        if admin and not user.has_permission(EVECredential.LIST_PERM):
            raise HTTPForbidden()
            
        credentials = user.credentials
        if admin:
            #Don't send the verification code for the API keys.
            credentials = EVECredential.objects.only('violation', 'key', 'verified', 'owner')

        return 'brave.core.key.template.list', dict(
                area='keys',
                admin=admin,
                records=credentials,
                rec_mask=config['core.recommended_key_mask'],
                rec_kind=config['core.recommended_key_kind']
            )

    @authenticate
    def post(self, **kw):
        data = Bunch(kw)
        
        try:
            data.key = int(data.key)
            if data.key <= int(config['core.minimum_key_id']):
                return 'json:', dict(success=False,
                                     message=_("The key given (%d) must be above minimum reset floor value of %d. "
                                               "Please reset your EVE API Key."
                                               % (data.key, int(config['core.minimum_key_id']))),
                                     field='key')
                
        except ValueError:
            return 'json:', dict(success=False, message=_("Key ID must be a number."), field='key')
        
        record = EVECredential(data.key, data.code, owner=user.id)
        
        try:
            record.save()
            #Necessary to guarantee that the pull finished before returning.
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
                        characters = characters,
                        violation = record.violation
                    )
        
        except ValidationError:
            if request.is_xhr:
                return 'json:', dict(
                            success=False,
                            message=_("Validation error: one or more fields are incorrect or missing."),
                    )
        except NotUniqueError:
            return 'json:', dict(
                success=False,
                message=_("This key has already been added to this or another account."),
            )

        raise HTTPFound(location='/key/')
 

class CorpKeyMaskController(Controller):
    """Controller for /key/mask/corp/"""
    
    def __lookup__(self, mask, *args, **kw):
        return CorpKeyMaskInterface(mask), args
        
        
class CorpKeyMaskInterface(HTTPMethod):
    """Interface for /key/mask/corp/{MASK}"""
    
    def __init__(self, mask):
        super(CorpKeyMaskInterface, self).__init__()
        self.mask = mask
        
    def get(self):
        funcs = EVECorporationKeyMask(int(self.mask)).functionsAllowed()
        return 'brave.core.key.template.maskDetails', dict(
            mask=self.mask,
            area='keys',
            functions=funcs,
            kind="Corporation"
        )
        
        
class KeyMaskController(Controller):
    """Controller for /key/mask/"""
    corp = CorpKeyMaskController()
    
    def __lookup__(self, mask, *args, **kw):
        return KeyMaskInterface(mask), args
        
        
class KeyMaskInterface(HTTPMethod):
    """Interface for /key/mask/{MASK}"""
    
    def __init__(self, mask):
        super(KeyMaskInterface, self).__init__()
        self.mask = mask
        
    def get(self):
        funcs = EVECharacterKeyMask(int(self.mask)).functionsAllowed()
        return 'brave.core.key.template.maskDetails', dict(
            mask=self.mask,
            area='keys',
            functions=funcs,
            kind="Character"
        )
        
        
class KeyController(Controller):
    """Entry point for the KEY management RESTful interface."""

    index = KeyList()
    mask = KeyMaskController()
    
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
