# encoding: utf-8

from web.core import Controller


class RootController(Controller):
    def index(self):
        return "adam.auth.template.test", dict()
    
    def authenticate(self):
        return "adam.auth.template.signin", dict()
