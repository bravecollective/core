# encoding: utf-8

from __future__ import unicode_literals

from web.core import request, url
from brave.core.api.util import SignedController


log = __import__('logging').getLogger(__name__)


class ApiController(SignedController):
    def ping(self, now=None):
        import calendar
        from datetime import datetime
        
        our = calendar.timegm(datetime.utcnow().utctimetuple())
        
        log.info("Recieved ping from %s, %s difference.",
                request.service.id, (our - int(now)) if now else "unknown")
        
        return dict(now=our)
    
    def authorize(self, success, failure):
        """Prepare a incoming session request."""
        
        return dict(
                youare = str(request.service.id),
                location = url.complete('/authorize/someidhere'),
                success = success,
                failure = failure
            )
