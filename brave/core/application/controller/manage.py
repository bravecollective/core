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
from brave.core.util.predicate import authenticate
from brave.core.permission.util import user_has_permission
from brave.core.permission.model import Permission
from brave.core.permission.controller import createPerms


log = __import__('logging').getLogger(__name__)


class ApplicationInterface(HTTPMethod):
    def __init__(self, app):
        super(ApplicationInterface, self).__init__()
        
        try:
            self.app = Application.objects.get(id=app)
        except Application.DoesNotExist:
            raise HTTPNotFound()

        if self.app.owner.id != user.id and not user.has_permission(self.app.edit_perm):
            raise HTTPNotFound()
    
    def get(self):
        app = self.app
        
        perms = ""
        
        for p in Permission.objects(id__startswith=(app.short + ".")):
            desc = p.description
            if not desc:
                desc = "None"
            perms += p.id + ":" + desc + "\n"
        
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
                            groups = app.groups,
                            short = app.short,
                            perms=perms,
                            expire = app.expireGrantDays,
                            all_chars = app.require_all_chars,
                            only_one_char = app.auth_only_one_char,
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
        
        # No dots in application shorts
        if '.' in valid['short']:
            return 'json:', dict(
                    success=False,
                    message=_("Stop being bad and remove the periods in your app short."))
        
        for k in ('name', 'description', 'groups', 'site', 'contact', 'development'):
            setattr(app, k, valid[k])
        
        if valid['key']['public'].startswith('-'):
            # Assume PEM format.
            valid['key']['public'] = hexlify(VerifyingKey.from_pem(valid['key']['public']).to_string())
        
        app.key.public = valid['key']['public']
        app.mask.required = valid['required'] or 0
        app.mask.optional = valid['optional'] or 0
        # Ignore their provided app short because we can't change permission names #ThanksMongo
        
        if user.admin:
            app.expireGrantDays = valid['expire'] or 30
            
        app.short = valid['short'] or app.name.replace(" ", "").lower()

        if valid['all_chars'] and valid['only_one_char']:
            return 'json:', dict(
                    success=False,
                    message=_("Cannot require both all characters and only one character"))
        app.require_all_chars = valid['all_chars'] or False
        app.auth_only_one_char = valid['only_one_char'] or False

        if valid['perms'] and not createPerms(valid['perms'], app.short):
            return 'json:', dict(
                    success=False,
                    message=_("Stop being bad and only include permissions for your app."))
        
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
    @authenticate
    def get(self):
        adminRecords = set()
        
        user_perms = user.permissions
        
        for app in Application.objects():
            if app.owner.id != user.id and Permission.set_grants_permission(user_perms, app.edit_perm):
                adminRecords.add(app)
        
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
    
    @user_has_permission(Application.CREATE_PERM)
    def post(self, **kw):
        if not request.is_xhr:
            raise HTTPNotFound()
        
        u = user._current_obj()
        valid, invalid = manage_form().native(kw)
        
        # No dots in application shorts
        if '.' in valid['short']:
            return 'json:', dict(
                    success=False,
                    message=_("Stop being bad and remove the periods in your app short."))
                    
        if len(Application.objects(short=valid['short'])):
            return 'json:', dict(
                    success=False,
                    message=_("An application with this permission name already exists."))

        app = Application(owner=u, **{k: v for k, v in valid.iteritems() if k in ('name', 'description', 'groups', 'site', 'contact')})
        
        app.key.public = valid['key']['public']
        app.mask.required = valid['required'] or 0
        app.mask.optional = valid['optional'] or 0

        if valid['all_chars'] and valid['only_one_char']:
            return 'json:', dict(
                    success=False,
                    message=_("Cannot require both all characters and only one character"))
        app.require_all_chars = valid['all_chars'] or False
        app.auth_only_one_char = valid['only_one_char'] or False
        
        if valid['development'] == "true" or valid['development'] == "True":
            app.development = True
        else:
            app.development = False

        app.short = valid['short'] or app.name.replace(" ", "").lower()
        
        if valid['perms'] and not createPerms(valid['perms'], app.short):
            return 'json:', dict(
                    success=False,
                    message=_("Stop being bad and only include permissions for your app."))
        
        p = Permission('core.application.authorize.{0}'.format(app.short), "Ability to authorize application {0}".format(app.name))
        p.save()
        if u.primary:
            u.primary.personal_permissions.append(p)
        u.primary.save()
        
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
