#!/usr/bin/env python

import sys, os
from setuptools import setup, find_packages

setup(
        name = "brave.core",
        version = "0.1",
        description = "EVE Online authentication, authorization, and API proxy service.",
        author = "Alice Bevan-McGregor",
        author_email = "alice@gothcandy.com",
        license = "MIT",
        
        packages = find_packages(),
        include_package_data = True,
        zip_safe = False,
        paster_plugins = ['PasteScript', 'WebCore'],
        namespace_packages = ['brave'],
        
        tests_require = ['nose', 'webtest', 'coverage', 'mock'],
        test_suite = 'nose.collector',
        
        install_requires = [
                'requests==1.1.0',
                'marrow.tags',
                'marrow.templating',
                'braveapi',
                'WebCore>=1.1.2,<2',
                'MongoEngine>=0.8,<0.9',
                'pymongo>=2,<3',
                'Mako>=0.4.1',
                'beaker>=1.5',
                'blinker',
                'pyyaml',
                'ecdsa',
                'relaxml',
                'ipython',
                'scrypt',
                'pudb',
                'webassets',
                'babel',
                'marrow.mailer',
                'yubico',
                'futures',
                'zxcvbn',
                'flake8',
                'evelink',
                'flup==1.0.2'
            ],

        setup_requires = [
                'PasteScript',
            ],
        
    )
