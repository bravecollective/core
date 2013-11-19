# encoding: utf-8

from __future__ import unicode_literals

from marrow.util.object import load_object


def load(area, cls):
    return load_object("brave.core.{}.controller:{}".format(area, cls))()
