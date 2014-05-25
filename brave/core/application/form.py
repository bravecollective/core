# encoding: utf-8

from __future__ import unicode_literals

from web.core.locale import L_
from marrow.widgets import Form, TextField, TextArea, SelectField, URLField, EmailField, CheckboxField
from marrow.widgets.transforms import TagsTransform
from brave.core.util.form import Tab, EmbeddedDocumentTab, Paragraph


log = __import__('logging').getLogger(__name__)


# TODO: Secondary form with additional 'owner' selector.
def manage_form(action='/application/manage/'):
    return Form('application', action=action, method='post', class_='modal-body tab-content form-horizontal', children=[
            Tab('general', L_("General"), class_='active', children=[
                    TextField('name', L_("Name"), required=True, class_="input-block-level validate"),
                    TextArea('description', L_("Description"), rows="6", class_='input-block-level'),
                    URLField('site', L_("Primary Site"), placeholder="http://", required=True, class_='input-block-level validate'),
                    EmailField('contact', L_("Primary Contact"), placeholder="user@example.com", class_='input-block-level'),
                    CheckboxField('development', L_("Development"), title="", class_='input-block-level'),
                ]),
            EmbeddedDocumentTab('key', L_("ECDSA Key"), labels=False, children=[
                    Paragraph('ecdsa', L_("You must generate a 256-bit NIST ECDSA key (using SHA256 hashing), hexlify or PEM encode the raw public key and paste it below.  The result should be 128 hexidecimal characters.")),
                    Paragraph('private', L_("Once your application has been registered the core service will generate its own application-specific key which you will need to configure your application to expect.")),
                    TextArea('public', placeholder=L_("Paste your application's public ECDSA key here."), rows=2, required=True, class_="input-block-level validate")
                ]),
            Tab('perms', L_("Permissions"), children=[
                    TextField('required', L_("Required Mask"), placeholder='0', class_="input-small"),
                    TextField('optional', L_("Optional Mask"), placeholder='0', class_="input-small"),
                    TextArea('groups', L_("Group Identifiers"), transform=TagsTransform(), placeholder="E.g.: fc diplo myapp myapp.special", rows=3, class_="input-block-level")
                ])
        ])
