# encoding: utf-8

from web.auth import authorize
from web.auth import CustomPredicate, Not, All, Any, anonymous, authenticated, AttrIn, ValueIn, EnvironIn


# Administrators are explicit.
is_administrator = AttrIn('admin', [True, ])

# Local users for development-only methods.
is_local = EnvironIn('REMOTE_ADDR', ('127.0.0.1', '::1', 'fe80::1%%lo0'))
