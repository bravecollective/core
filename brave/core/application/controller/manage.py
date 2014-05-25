# encoding: utf-8

from __future__ import unicode_literals

from binascii import hexlify, unhexlify
from hashlib import sha256
from ecdsa.keys import SigningKey, VerifyingKey
from ecdsa.curves import NIST256p

from web.auth import user
from web.core import Controller, HTTPMethod, request
from web.core.locale import _
from web.core.http import HTTPFound, HTTPNotFound

from brave.core.application.model import Application
from brave.core.application.form import manage_form
from brave.core.util.predicate import authorize, authenticated, is_administrator


log = __import__('logging').getLogger(__name__)


class ApplicationInterface(HTTPMethod):
    def __init__(self, app):
        super(ApplicationInterface, self).__init__()
        
        try:
            self.app = Application.objects.get(id=app)
        except Application.DoesNotExist:
            raise HTTPNotFound()

        if self.app.owner.id != user.id and not user.admin:
            raise HTTPNotFound()
    
    def get(self):
        app = self.app
        
        if request.is_xhr:
            return 'brave.core.template.form', dict(
                    kind = _("Application"),
                    form = manage_form('/application/manage/{0}'.format(app.id)),
                    data = dict(
                            name = app.name,
                            description = app.description,
                            site = app.site,
                            contact = app.contact,
                            development = app.development,
                            key = dict(
                                    public = app.key.public,
                                    private = app.key.private,
                                ),
                            required = app.mask.required,
                            optional = app.mask.optional,
                            groups = app.groups
                        )
                )
        
        key = SigningKey.from_string(unhexlify(app.key.private), curve=NIST256p, hashfunc=sha256)
        return 'brave.core.application.template.view_app', dict(
                app = app,
                key = hexlify(key.get_verifying_key().to_string()),
                pem = key.get_verifying_key().to_pem()
            )
    
    def post(self, **kw):
        if not request.is_xhr:
            raise HTTPNotFound()
        
        app = self.app
        valid, invalid = manage_form().native(kw)
        
        for k in ('name', 'description', 'groups', 'site', 'contact', 'development'):
            setattr(app, k, valid[k])
        
        if valid['key']['public'].startswith('-'):
            # Assume PEM format.
            valid['key']['public'] = hexlify(VerifyingKey.from_pem(valid['key']['public']).to_string())
        
        app.key.public = valid['key']['public']
        app.mask.required = valid['required'] or 0
        app.mask.optional = valid['optional'] or 0
        
        app.save()
        
        return 'json:', dict(
                success = True,
            )
    
    def delete(self):
        log.info("Deleted application %s owned by %s", self.app, self.app.owner)
        
        self.app.delete()

        if request.is_xhr:
            return 'json:', dict(
                    success = True,
                    message = _("Successfully deleted application registration.")
                )

        raise HTTPFound(location='/application/manage/')


class ApplicationList(HTTPMethod):
    @authorize(authenticated)
    def get(self):
        if user.admin:
            adminRecords = {record for record in Application.objects() if record.owner != user._current_obj()}
        else:
            adminRecords = {}
        
        records = Application.objects(owner=user._current_obj())
        
        if request.is_xhr:
            return 'brave.core.template.form', dict(
                    kind = _("Application"),
                    form = manage_form(),
                    data = None,
                )
        
        return 'brave.core.application.template.manage_apps', dict(
                area = 'apps',
                records = records,
                adminRecords = adminRecords
            )
    
    @authorize(authenticated)
    def post(self, **kw):
        if not request.is_xhr:
            raise HTTPNotFound()
        
        u = user._current_obj()
        valid, invalid = manage_form().native(kw)
        
        app = Application(owner=u, **{k: v for k, v in valid.iteritems() if k in ('name', 'description', 'groups', 'site', 'contact')})
        
        app.key.public = valid['key']['public']
        app.mask.required = valid['required'] or 0
        app.mask.optional = valid['optional'] or 0
        
        if valid['development'] == "true" or valid['development'] == "True":
            app.development = True
        else:
            app.development = False
        
        app.save()
        
        return 'json:', dict(
                success = True,
                location = '/application/manage/'
            )


class ManagementController(Controller):
    index = ApplicationList()
    
    def __lookup__(self, app, *args, **kw):
        request.path_info_pop()  # We consume a single path element.
        return ApplicationInterface(app), args
