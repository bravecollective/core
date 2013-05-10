# encoding: utf-8

from web.core import Controller


class RootController(Controller):
    def index(self):
        return "hi!"
