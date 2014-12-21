from mongoengine import Document, EmbeddedDocument, EmbeddedDocumentField, DictField, StringField, EmailField, URLField, DateTimeField, BooleanField, ReferenceField, ListField, IntField

# Core Legacy Storage
class ApplicationKeys(EmbeddedDocument):
    meta = dict(
            allow_inheritance = False,
        )

    public = StringField(db_field='u')  # Application public key.
    private = StringField(db_field='r')  # Server private key.


class CoreLegacyStorage(EmbeddedDocument):
    key = EmbeddedDocumentField(ApplicationKeys, db_field='k', default=lambda: ApplicationKeys())


# OAuth2 Authorization Code Storage
class OAuth2ACStorage(EmbeddedDocument):
    redirect_uri = URLField(regex=r'^https://')  # TODO: Fix regex
    client_secret = StringField(min_length=64)
    grant_type = StringField(choices=['authorization_code'])


class ApplicationMasks(EmbeddedDocument):
    meta = dict(
            allow_inheritance = False,
        )

    required = IntField(db_field='r', default=0)
    optional = IntField(db_field='o', default=0)

    def __repr__(self):
        return 'Masks({0}, {1})'.format(self.required, self.optional)

class Application(Document):
    meta = dict(
            collection = 'Applications',
            allow_inheritance = False,
            indexes = [],
            ordering = ('name', )
        )

    # Field Definitions

    name = StringField(db_field='n')
    description = StringField(db_field='d')
    site = URLField(db_field='s')
    contact = EmailField(db_field='c')

    # This is the short name of the application, which is used for permissions. Must be lowercase.
    short = StringField(db_field='p', unique=True, regex='[a-z]+', required=True)

    mask = EmbeddedDocumentField(ApplicationMasks, db_field='m', default=lambda: ApplicationMasks())
    groups = ListField(StringField(), db_field='g', default=list)
    development = BooleanField(db_field='dev')
    # Number of days that grants for this application should last.
    expireGrantDays = IntField(db_field='e', default=30)

    auth_methods = ListField(StringField(choices=['oauth2ac', 'core_legacy']))

    oauth2ac = EmbeddedDocumentField(OAuth2ACStorage, default=lambda: OAuth2ACStorage())
    core_legacy = EmbeddedDocumentField(CoreLegacyStorage,default=lambda: CoreLegacyStorage())

    # This field indicates whether the application requires access to every character on the authorizing user's account.
    require_all_chars = BooleanField(db_field='a', default=False)
    auth_only_one_char = BooleanField(db_field='one', default=False)

    owner = ReferenceField('User', db_field='o')

    key = EmbeddedDocumentField(ApplicationKeys, db_field='k', default=lambda: ApplicationKeys())


def auth_method_migration(dry_run=True):
    x = 0
    for a in Application.objects:
        x += 1
        if not dry_run:
            a.core_legacy.key = a.key
            a.key = None
            a.save()

    print("Updated {} applications.".format(x))
