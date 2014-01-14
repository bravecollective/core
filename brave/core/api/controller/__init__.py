# encoding: utf-8

from __future__ import unicode_literals

from web.core import request

from brave.core.api.model import AuthenticationRequest
from brave.core.api.util import SignedController
from brave.core.api.controller.core import CoreAPI


log = __import__('logging').getLogger(__name__)


class ApiController(SignedController):
    core = CoreAPI()
    
    def ping(self, now=None):
        import calendar
        from datetime import datetime
        
        our = calendar.timegm(datetime.utcnow().utctimetuple())
        
        log.info("Recieved ping from %s, %s difference.",
                request.service.id, (our - int(now)) if now else "unknown")
        
        return dict(now=our)
