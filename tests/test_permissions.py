import unittest

from brave.core.account.model import User
from brave.core.character.model import EVECharacter
from brave.core.permission.model import Permission, WildcardPermission
from brave.core.group.model import Group

class PermissionTest(unittest.TestCase):
    def setUp(self):
        # Clear permissions from the database
        for p in Permission.objects():
            p.delete()
            
        # Clear groups from the database
        for g in Group.objects():
            g.delete()
            
    def createWild(self, name):
        p = WildcardPermission(name)
        p.save()
        return p
        
    def createPerm(self, name):
        p = Permission(name)
        p.save()
        return p
        
    def createPermsTest(self):
        Permission('core.hello').save()
        Permission('core.test').save()
        Permission('core.test.no').save()
        Permission('core.permission.grant').save()
        Permission('mumble.join').save()
        Permission('mumble.server.join').save()
        Permission('mumble.test').save()
        WildcardPermission('*').save()
        WildcardPermission('*.test').save()
        WildcardPermission('core.*').save()
            
    def test_runtime_perm(self):
        check_perm = 'core.test.wildcard.permission'
        self.assertTrue(self.createWild('*').grants_permission(check_perm))
        self.assertTrue(self.createWild('core.*').grants_permission(check_perm))
        self.assertTrue(self.createWild('core.test.*').grants_permission(check_perm))
        self.assertTrue(self.createWild('core.test.wildcard.*').grants_permission(check_perm))
        self.assertTrue(self.createWild('core.test.*.permission').grants_permission(check_perm))
        self.assertTrue(self.createWild('core.*.wildcard.permission').grants_permission(check_perm))
        self.assertTrue(self.createWild('core.*.wildcard.*').grants_permission(check_perm))
        self.assertFalse(self.createWild('test.*').grants_permission(check_perm))
        self.assertFalse(self.createWild('core.te.*').grants_permission(check_perm))
        self.assertFalse(self.createWild('core.test.wildcard.*.hello').grants_permission(check_perm))
        self.assertFalse(self.createWild('core.*.wildcard.*.hello').grants_permission(check_perm))
        
    def test_wildcard_evaluation(self):
        check_perm = Permission('core.test.wildcard.permission')
        check_perm.save()
        check_perm = check_perm.id
        self.assertTrue(self.createWild('*').grants_permission(check_perm))
        self.assertTrue(self.createWild('core.*').grants_permission(check_perm))
        self.assertTrue(self.createWild('core.test.*').grants_permission(check_perm))
        self.assertTrue(self.createWild('core.test.wildcard.*').grants_permission(check_perm))
        self.assertTrue(self.createWild('core.test.*.permission').grants_permission(check_perm))
        self.assertTrue(self.createWild('core.*.wildcard.permission').grants_permission(check_perm))
        self.assertTrue(self.createWild('core.*.wildcard.*').grants_permission(check_perm))
        self.assertFalse(self.createWild('test.*').grants_permission(check_perm))
        self.assertFalse(self.createWild('core.te.*').grants_permission(check_perm))
        self.assertFalse(self.createWild('core.test.wildcard.*.hello').grants_permission(check_perm))
        self.assertFalse(self.createWild('core.*.wildcard.*.hello').grants_permission(check_perm))
        
    def test_group_permissions(self):
        self.createPermsTest()
        g = Group(id='testGroup')
        g._permissions.append(Permission.objects(id='*.test').first())
        g._permissions.append(Permission.objects(id='core.permission.grant').first())
        g.save()
        self.assertTrue(Permission.set_grants_permission(g.permissions, 'core.test'))
        self.assertTrue(Permission.set_grants_permission(g.permissions, 'mumble.test'))
        self.assertTrue(Permission.set_grants_permission(g.permissions, 'core.permission.grant'))
        self.assertTrue(Permission.set_grants_permission(g.permissions, '*.test'))
        self.assertEqual(set([p.id for p in g.permissions]),
                         set(['core.permission.grant',
                              '*.test']))
