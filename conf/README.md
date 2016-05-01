# Core INI Config Files

Core uses multiple `.ini` files to define config options. Each config file maps to a desired environment. 
We name the example file `development.ini` because you can freely copy/edit/revert it and play around with the ini settings.

For production, we default to enforcing a ini file named `production.ini` for all your production settings and options. 
You are free to name these files however you want, you will just need to update where they are referenced. 
You can also make any number of duplicate files and reference them directly when starting a paster instance. 

    $ paster shell conf/$NAME.ini

## shard-{n}.ini

There are two shard ini files here, these are used to setup the FastCGI sockets, and used in the `service-core` bin script. 
You might need to look them over and make sure that filesystem paths look correct for your install, 
but otherwise these don't need any customization.

## development.ini

Brave Core is built on top of [WebCore](http://pythonhosted.org/WebCore/). WebCore's recommended environment and 
serving system is paster, and it ships with a few useful paster commands that make working with WebCore very simple. 
If you have questions about how something works in BraveCore, you should look at the WebCore documentation if your lost. 

WebCore is essentially a set of packages and glue that binds them all together. You setup your application state with these 
config file settings. See below for some basic documentation on what they are and do.

When you understand these config options, you should copy the included `development.ini` file to `production.ini` 
and set your production values there. All supplied helper files and scripts rely on a `production.ini` file existing.

### WebCore RootController

WebCore works on the front controller pattern, where one main controller sets up access to all other controllers. We 
define that controller here

#### web.root

The root controller of you Core Install. 

> You should never change this.

```ini
web.root = brave.core.controller:RootController
```

### WebCore Cache Settings

Caching is provided by beaker: https://beaker.readthedocs.org/en/latest/ 

#### web.cache

Use this to turn on/off WebCore caching. 

Should not have to change this.

> You should never change this.

```ini
web.cache = True
```

#### web.cache.data_dir

The location of the cache files on disk.

```ini
web.cache.data_dir = /home/core/var/cache
```

#### web.cache.regions

See relevant beaker configs: https://beaker.readthedocs.org/en/latest/caching.html#cache-regions

```ini
web.cache.regions = general, texting
```

#### web.cache.general.expire

Default cache expiry time for the general region, set to 1 day by default.

```ini
web.cache.general.expire = 86400
```

#### web.cache.texting.expire

Default cache expiry time for the general region, set to 7 days by default.

```ini
web.cache.texting.expire = 604800
```

### WebCore Session Settings

Sessions are provided by beaker: https://beaker.readthedocs.org/en/latest/

You should read this and make sure you have a proper cron job setup to delete these sessions at regular intervals: 
https://beaker.readthedocs.org/en/latest/sessions.html#removing-expired-old-sessions 

Sessions in core default to filesystem storage unless you create a new setting: `web.sessions.type = cookie`

#### web.sessions

Use this to turn on/off WebCore sessions.

> You should never change this.

```ini
web.sessions = True
```

#### web.sessions.secure

Enable encrypted sessions?

> You should never change this.

```ini
web.sessions.secure = True
```

#### web.sessions.data_dir

The location on disk to store session data files

```ini
web.sessions.data_dir = /home/core/var/session
```

#### web.sessions.lock_dir

The location on disk to store session lock files

```ini
web.sessions.lock_dir = /home/core/var/locks
```

### WebCore i18n Settings 

WebCore ships with i18n internationalization support. i18n support is provided by [Babel](http://babel.pocoo.org/)

#### web.locale.i18n

Enable i18n support?

> You should never change this.

```ini
web.locale.i18n = True
```

#### web.locale.path

The filesystem location of you locale files

> You should never have to change this.

```ini
web.locale.path = %(here)s/../brave/core/locale
```

#### web.locale.fallback

The local to fall back to if a language bit does not exist for a specific locale.

```ini
web.locale.fallback = en
```

### WebCore User Authentication Settings

WebCore uses an app model and authentication routine to enable user accounts and data. This is all setup here, and 
should never need to be changed.

#### web.auth

Enable user authentication support?

> You should never change this.

```ini
web.auth = True
```

#### web.auth.name

Model to use for user authentication.

> You should never change this.

```ini
web.auth.name = user
```

#### web.auth.authenticate

The method to call when trying to validate a user login

> You should never change this.

```ini
web.auth.authenticate = brave.core.account.authentication:authenticate
```

#### web.auth.lookup

The method to call when trying to lookup a user

> You should never change this.

```ini
web.auth.lookup = brave.core.account.authentication:lookup
```

#### web.auth.handler

The URI to send unauthenticated users to to authenticate

> You should never change this.

```ini
web.auth.handler = /account/authenticate
```

#### web.auth.intercept

The HTTP error code to return if a user is not authenticated.

> You should never change this.

```ini
web.auth.intercept = 401
```

### WebCore Static Files Settings 

WebCore enables serving and compiling static files from a specific folder in you core setup. These settings should not 
need to be changed, but are documented here for completeness.

#### web.static

This enables service "static" files like JS or CSS or Font files out of a directory that a web browser will be able to 
sanely query. 

> You should never change this.

```ini
web.static = True
```

#### web.static.path

The location of your static files folder.

> You should never have to change this.

```ini
web.static.path = %(here)s/../brave/core/public
```

#### web.static.base

The base URI to map the static folder to.

> You should never have to change this.

```ini
web.static.base = /
```

#### web.static.compiled

The location to call compiled assets from.

> You should never have to change this.

```ini
web.static.compiled = /_static
```

### WebCore Templating Renderer

#### web.templating.engine

WebCore supports multiple template compiling/rendering engines. Brave Core uses the Mako template engine and we 
configure this here.

> You should never have to change this.

```ini
web.templating.engine = mako
```

### Advanced Debugging

#### debug

This enables advanced debugging capabilities when encountering python exceptions.

These capabilities allow remote code execution, this should ALWAYS be False in production.

```ini
debug = False
```

### Database Connections

Brave Core uses MongoDB for its database backend. You will need to be running at least 2.8.* of mongodb-server. We 
highly recommend that you set mongodb to only listen to localhost, and to set a username/password on your database.

#### db.connections

This is the db connection to use by default. We configure the main db settings below.

> You should never have to change this.

```ini
db.connections = main
```

#### db.main.engine

Which Database engine to use. BraveCore Uses Mongoengine.

> You should never have to change this.

```ini
db.main.engine = mongoengine
```

#### db.main.model

This is the root model that is loaded automatically. Brave uses domain specific models, so this directs to an empty file.

> You should never have to change this.

```ini
db.main.model = brave.core.model
```

#### db.main.url

The database connection URI. Fill in your specific database connection information here.

```ini
db.main.url = mongo://username:password@localhost/core
```

### Mail transport

eMail is delivered by marrow.mail, a package included during setup. .mail supports a wide variety of mail delivery 
agents and patterns, we have setup SMTP as the default delivery agent and specified some example configuration below.

#### mail.manager.use

Which mail processing system to use. BraveCore elects to enable instant mail delivery, which is the best experience for the user.

> You should never have to change this.

```ini
mail.manager.use = immediate
```

#### mail.transport.use

Which mail transport technology to use. We reccomend TLS encrypted SMTP here, and we configure as such below.

> You should never have to change this.

```ini
mail.transport.use = smtp
```

#### mail.transport.host

The SMPT hostname that sends your mail. Mailgun is a great choice and will deliver 10k emails a month for free forever.

```ini
mail.transport.host = smtp.mailgun.org
```

#### mail.transport.username

The username you use to connect to your SMTP host

```ini
mail.transport.username = helloworld
```

#### mail.transport.password

The password you use to connect to your SMTP host

```ini
mail.transport.password = 123456
```

#### mail.transport.port

The port you use to connect to your SMTP host

```ini
mail.transport.port = 25
```

#### mail.transport.local_hostname

Your local app hostname

```ini
mail.transport.local_hostname = core.braveineve.com
```

#### mail.transport.timeout

TCP Connection timeout in seconds

```ini
mail.transport.timeout = 60
```

#### mail.transport.tls

Set to True to force TLS HELLO connections

```ini
mail.transport.tls = True
```

#### mail.transport.debug

Leave this off unless you know what your doing.

> You should never have to change this.

```ini
mail.transport.debug = False
```

### Mail Sender 

This is identifying information about your mail user, please make sure this information is accurate.

#### mail.message.author

The from name and address for all sent mail

```ini
mail.message.author = Brave Collective Core Services <core@braveineve.com>
```

#### mail.message.organization

The organization/company name of the entity sending mail

```ini
mail.message.organization = Brave Collective
```

### Yubico

[Yubico](https://www.yubico.com/) is an encrypted password USB key that enables secure user authentication without users 
having to remember username/password combos or long secrets. You will need a yubikey developer account to enable this.

#### yubico.client

The Yubico client ID for your developer account

```ini
yubico.client = 
```

#### yubico.key

The Yubico client key for your developer account

```ini
yubico.key =
```

#### yubico.secure

Enable secure logins with Yubico?

```ini
yubico.secure = True
```

### Brave API

This is the location of the Brave Core API endpoints in core. You need to make sure you have generated a secure private ECC 
key, and set it here.

#### api.endpoint

The URI where Core's API is setup. This is always {domain}/api, so just correct the domain portion to suit your install.

```ini
api.endpoint = http://core.braveineve.net/api
```

#### api.identity

This is mainly used by applications that connect to core via its API. You can ignore this for your core install.

> You should never have to set this.

```ini
api.identity = 
```

#### api.key

This is where you set your applications Private ECC key. See main documentation for generating this key.

```ini
api.key = 
```

### General CORE Settings

Core has grown over the years, and a few of the additions have been exposed as configurable settings. These settings 
are described below.

#### core.required_pass_strength

Core uses the zxcvbn password strength library, and that library exposes a strength approximation via integer. You can enforce 
a minimum password complexity with this setting. 2 is the default, for the paranoid, set this to 3. If you do set this to 3, 
it's likely your users will complain endlessly over it. 

```ini
core.required_pass_strength = 2
```

#### core.minimum_key_id

This is a setting to enforce a minimum EVE Key ID. 

This setting is Deprecated

```ini
core.minimum_key_id = 3283828
```

#### core.recommended_key_mask

This is the recommended default API key minimum mask that core will accept form users.

```ini
core.recommended_key_mask = 59695480
```

#### core.recommended_key_kind

This is the key type minimum that will be accepted by core. If you don't care about having Account API keys, you 
can set this to `Character`

```ini
core.recommended_key_kind = Account
```

#### core.require_recommended_key

This setting will enforce the minimum key mask set above as the valid minimum info data.

```ini
core.require_recommended_key = True
```

#### core.login_history_days

How long to store Login History data for each user (Ip Address, User Account) pairs.

```ini
core.login_history_days = 300000
```

#### core.operator

This is used to set the User-Agent when sending the EVE Api requests. They request that this be a name and email address to 
contact your IT team if something goes wrong.

```ini
core.operator = 'Brave Collective IT (it@bravecollective.com)'
```