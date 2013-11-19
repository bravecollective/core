# encoding: utf-8

from __future__ import unicode_literals

from marrow.util.object import load_object


def load(area):
    return load_object("brave.core.{}.controller:{}Controller".format(area, area.title()))()
