#!/usr/bin/env python

import sys, os
from setuptools import setup, find_packages

setup(
        name = "ADAM",
        version = "0.1",
        description = "An EVE-authenticated collection of utilities, like a wiki.",
        author = "Alice Bevan-McGregor",
        author_email = "alice@gothcandy.com",
        license = "MIT",
        packages = find_packages(),
        include_package_data = True,
        paster_plugins = ['PasteScript', 'WebCore'],
        install_requires = ['WebCore', 'MongoEngine', 'Mako', 'beaker', 'pyyaml', 'ecdsa', 'xmltodict', 'ipython', 'scrypt'],
        namespace_packages = ['adam'],
    )
