# encoding: utf-8

from __future__ import unicode_literals

from braveapi.controller import SignedController as OriginalSignedController
from brave.core.application.model import Application


log = __import__('logging').getLogger(__name__)


class SignedController(OriginalSignedController):
    def __service__(self, identifier):
        return Application.objects.get(id=identifier)
