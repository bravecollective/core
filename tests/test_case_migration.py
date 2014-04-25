import unittest

from brave.core.account.model import User
from brave.core.scripts import case_migration

class CaseMigrationTest(unittest.TestCase):
    def setUp(self):
        # clear users from the database
        for u in User.objects:
            u.delete()

    def check_user(self, id, username, email):
        u = User.objects(id=id)[0]
        self.assertEqual(u.username, username)
        self.assertEqual(u.email, email)

    def test_no_change_case(self):
        id = User(username="user", email="user@example.com").save().id

        case_migration.migrate()

        self.assertEqual(len(User.objects), 1)
        self.check_user(id, "user", "user@example.com")

    def test_lowercased(self):
        id = User(username="UsEr", email="USER@EXAMPLE.COM").save(validate=False).id

        case_migration.migrate()

        self.assertEqual(len(User.objects), 1)
        self.check_user(id, "user", "user@example.com")

    def test_username_collision(self):
        id1 = User(username="user", email="user1@example.com").save().id
        id2 = User(username="UsEr", email="user2@example.com").save(validate=False).id

        failures = case_migration.migrate()

        self.assertEqual(len(User.objects), 2)
        self.check_user(id1, "user", "user1@example.com")
        self.check_user(id2, "UsEr", "user2@example.com") # colliding user not modified
        self.assertEqual(len(failures), 1)

    def test_email_collision(self):
        id1 = User(username="user1", email="user@example.com").save().id
        id2 = User(username="user2", email="USER@example.com").save(validate=False).id

        failures = case_migration.migrate()

        self.assertEqual(len(User.objects), 2)
        self.check_user(id1, "user1", "user@example.com")
        self.check_user(id2, "user2", "USER@example.com") # colliding user not modified
        self.assertEqual(len(failures), 1)
