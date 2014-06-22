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
        p = WildcardPermission(name=name)
        p.save()
        return p
        
    def createPerm(self, name):
        p = Permission(name=name)
        p.save()
        return p
        
    def createPermsTest(self):
        Permission(name='core.hello').save()
        Permission(name='core.test').save()
        Permission(name='core.test.no').save()
        Permission(name='core.permission.grant').save()
        Permission(name='mumble.join').save()
        Permission(name='mumble.server.join').save()
        Permission(name='mumble.test').save()
        WildcardPermission(name='*').save()
        WildcardPermission(name='*.test').save()
        WildcardPermission(name='core.*').save()
            
    def test_runtime_perm(self):
        check_perm = 'core.test.wildcard.permission'
        self.assertTrue(self.createWild('*').grantsPermission(check_perm))
        self.assertTrue(self.createWild('core.*').grantsPermission(check_perm))
        self.assertTrue(self.createWild('core.test.*').grantsPermission(check_perm))
        self.assertTrue(self.createWild('core.test.wildcard.*').grantsPermission(check_perm))
        self.assertTrue(self.createWild('core.test.*.permission').grantsPermission(check_perm))
        self.assertTrue(self.createWild('core.*.wildcard.permission').grantsPermission(check_perm))
        self.assertTrue(self.createWild('core.*.wildcard.*').grantsPermission(check_perm))
        self.assertFalse(self.createWild('test.*').grantsPermission(check_perm))
        self.assertFalse(self.createWild('core.te.*').grantsPermission(check_perm))
        self.assertFalse(self.createWild('core.test.wildcard.*.hello').grantsPermission(check_perm))
        self.assertFalse(self.createWild('core.*.wildcard.*.hello').grantsPermission(check_perm))
        
    def test_wildcard_evaluation(self):
        check_perm = Permission(name='core.test.wildcard.permission')
        check_perm.save()
        check_perm = check_perm.name
        self.assertTrue(self.createWild('*').grantsPermission(check_perm))
        self.assertTrue(self.createWild('core.*').grantsPermission(check_perm))
        self.assertTrue(self.createWild('core.test.*').grantsPermission(check_perm))
        self.assertTrue(self.createWild('core.test.wildcard.*').grantsPermission(check_perm))
        self.assertTrue(self.createWild('core.test.*.permission').grantsPermission(check_perm))
        self.assertTrue(self.createWild('core.*.wildcard.permission').grantsPermission(check_perm))
        self.assertTrue(self.createWild('core.*.wildcard.*').grantsPermission(check_perm))
        self.assertFalse(self.createWild('test.*').grantsPermission(check_perm))
        self.assertFalse(self.createWild('core.te.*').grantsPermission(check_perm))
        self.assertFalse(self.createWild('core.test.wildcard.*.hello').grantsPermission(check_perm))
        self.assertFalse(self.createWild('core.*.wildcard.*.hello').grantsPermission(check_perm))
        
    def test_group_permissions(self):
        self.createPermsTest()
        g = Group(id='testGroup')
        g._permissions.append(Permission.objects(name='*.test').first())
        g._permissions.append(Permission.objects(name='core.permission.grant').first())
        g.save()
        self.assertEqual(g.permissions, set({Permission.objects(name='core.test').first(),
            Permission.objects(name='mumble.test').first(), Permission.objects(name='core.permission.grant').first(),
            Permission.objects(name='*.test').first()}))
