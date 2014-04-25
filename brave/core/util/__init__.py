# encoding: utf-8

from __future__ import unicode_literals

import re
from HTMLParser import HTMLParser
from marrow.util.object import load_object


def load(area):
    return load_object("brave.core.{}.controller:{}Controller".format(area, area.title()))()


class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []
    
    def handle_data(self, d):
        self.fed.append(d)
    
    def get_data(self):
        return ''.join(self.fed)


def strip_tags(html):
    txt = re.sub('<[^>]+>', '', html)
    return re.sub('\s+', ' ', txt)
    
    #s = MLStripper()
    #s.feed(html)
    #return s.get_data()
