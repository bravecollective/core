import mock
import unittest

from brave.core.group.model import Group, CyclicGroupReference, GroupReferenceException
from brave.core.group.acl import ACLRule, ACLGroupMembership


class ACLGroupMembershipTestCase(unittest.TestCase):
    def tearDown(self):
        Group.drop_collection()

    def assertCantDelete(self, g):
        with self.assertRaises(GroupReferenceException):
            g.delete()
        self.assertEqual(1, len(Group.objects(id=g.id)))
        with self.assertRaises(GroupReferenceException):
            Group.objects(id=g.id).delete()
        self.assertEqual(1, len(Group.objects(id=g.id)))

    def test_membership(self):
        class ACLTrue(ACLRule):
            def evaluate(self, user, character, _context=None):
                return True

        class ACLFalse(ACLRule):
            def evaluate(self, user, character, _context=None):
                return False

        u = mock.Mock()
        c = mock.Mock()

        g1 = Group(id='g1').save()

        g1.rules = [ACLTrue()]
        g1.save()

        self.assertIs(True, ACLGroupMembership(group=g1, grant=True, inverse=False).evaluate(u, c))
        self.assertIs(False, ACLGroupMembership(group=g1, grant=False, inverse=False).evaluate(u, c))
        self.assertIs(None, ACLGroupMembership(group=g1, grant=True, inverse=True).evaluate(u, c))
        self.assertIs(None, ACLGroupMembership(group=g1, grant=False, inverse=True).evaluate(u, c))

        g1.rules = [ACLFalse()]
        g1.save()

        self.assertIs(None, ACLGroupMembership(group=g1, grant=True, inverse=False).evaluate(u, c))
        self.assertIs(None, ACLGroupMembership(group=g1, grant=False, inverse=False).evaluate(u, c))
        self.assertIs(True, ACLGroupMembership(group=g1, grant=True, inverse=True).evaluate(u, c))
        self.assertIs(False, ACLGroupMembership(group=g1, grant=False, inverse=True).evaluate(u, c))

    def test_recursion_check(self):

        g1 = Group(id='g1').save()
        g2 = Group(id='g2').save()

        g1.rules = [ACLGroupMembership(group=g2)]
        g1.save()

        g2.rules = [ACLGroupMembership(group=g1)]
        with self.assertRaises(CyclicGroupReference):
            g2.save()

    def test_deletion_check(self):
        g1 = Group(id='g1').save()
        g2 = Group(id='g2').save()

        g2.rules = [ACLGroupMembership(group=g1)]
        g2.save()
        self.assertCantDelete(g1)

        g2.rules = []
        g2.request_rules = [ACLGroupMembership(group=g1)]
        g2.save()
        self.assertCantDelete(g1)

        g2.request_rules = []
        g2.join_rules = [ACLGroupMembership(group=g1)]
        g2.save()
        self.assertCantDelete(g1)

    def test_rename(self):
        g1 = Group(id='g1').save()
        g2 = Group(id='g2').save()

        g2.rules = [ACLGroupMembership(group=g1)]
        g2.save()

        g1_renamed = g1.rename('new_group')

        self.assertEqual(Group.objects(id='g2').first().rules[0].group.id, g1_renamed.id)
