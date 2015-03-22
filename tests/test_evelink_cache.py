"""Shamelessly cribbed from evelink's test suite and modified."""

import unittest

from brave.core.util.evelink import EvelinkAPICacheEntry, MongoCache

class MongoCacheTestCase(unittest.TestCase):

    def setUp(self):
        self.cache = MongoCache()

    def tearDown(self):
        EvelinkAPICacheEntry.objects().delete()

    def test_cache(self):
        self.cache.put('foo', 'bar', 3600)
        self.cache.put('bar', 1, 3600)
        self.cache.put('baz', True, 3600)
        self.assertEqual(self.cache.get('foo'), 'bar')
        self.assertEqual(self.cache.get('bar'), 1)
        self.assertEqual(self.cache.get('baz'), True)

    def test_expire(self):
        self.cache.put('baz', 'qux', -1)
        self.assertEqual(self.cache.get('baz'), None)
