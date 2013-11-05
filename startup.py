#!/usr/bin/env python

import os
import sys

import paste.fixture
import paste.registry
import paste.deploy.config

from paste.deploy import loadapp, appconfig


if os.path.exists('local.ini'):
    config_name = 'config:local.ini'
else:
    config_name = 'config:development.ini'
here_dir = os.getcwd()

conf = appconfig(config_name, relative_to=here_dir)
conf.update(dict(app_conf=conf.local_conf, global_conf=conf.global_conf))
paste.deploy.config.CONFIG.push_thread_config(conf)

# Load locals and populate with objects for use in shell
sys.path.insert(0, here_dir)

# Load the wsgi app first so that everything is initialized right
wsgiapp = loadapp(config_name, relative_to=here_dir)
test_app = paste.fixture.TestApp(wsgiapp)

# Query the test app to setup the environment
tresponse = test_app.get('/_test_vars')
request_id = int(tresponse.body)

# Disable restoration during test_app requests
test_app.pre_request_hook = lambda self: paste.registry.restorer.restoration_end()
test_app.post_request_hook = lambda self: paste.registry.restorer.restoration_begin(request_id)

paste.registry.restorer.restoration_begin(request_id)


import web
from web.core import http, Controller, request, response, cache, session
