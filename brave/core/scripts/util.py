from datetime import datetime
from brave.core.account.model import User

def time_function(func, *args, **kwargs):
    before = datetime.now()
    res = func(*args, **kwargs)
    after = datetime.now()
    print "Function took {0} and returned {1}".format(after-before, str(res))

def get_acid():
    return User.objects(username='acid katelo').first()
