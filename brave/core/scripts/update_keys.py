from time import sleep
from brave.core.key.model import EVECredential
import random
from threading import Thread
from datetime import datetime, timedelta

keys = dict()

class CredentialUpdateThread(Thread):
    def __init__(self, indices):
        super(CredentialUpdateThread, self).__init__()
        self.indices = indices
    
    def next_index_time(self):
        mins = datetime.now().hour * 60 + datetime.now().minute
        for i in self.indices:
            if i > mins:
                return i
        return self.indices[0] + 24*60
    
    def run(self):
        while True:
            now = datetime.now()
            next_index = now + timedelta(minutes=self.next_index_time()-(now.minute+60*now.hour))
            next_index = next_index - timedelta(microseconds=(next_index.microsecond + next_index.second*1000000))
            sleep((next_index-datetime.now()).total_seconds())
            now = datetime.now()
            if (now.minute+60*now.hour) not in keys.keys():
                continue
            for k in keys[(now.minute+60*now.hour)]:
                self.update_key(k)
        
                    
    @staticmethod
    def update_key(k):
        key = EVECredential.objects(key=k).first()
        try:
            print "Pulling key ID {0}".format(k)
            key_result = key.pull()
        except HTTPError as e:
            print("Error {}: {}".format(e.response.status_code, e.response.text))
        if not key_result:
            print("Removed disabled key {0} from account {1} with characters {2}".format(k, key.owner, key.characters))

def main(time_between_pulls=1440, threads=1):
    """ Max supported int for time_between_pulls is 1440, setting time_between_pulls less than threads will probably
        cause problems, so don't do it. This script makes no guarentee of thread safety, so using more than 1 thread
        is strongly discouraged if you value your database's integrity."""
    # Seed the keys into a dictionary, sorted by randomly assigned integers
    for k in EVECredential.objects():
        index = random.randint(0, time_between_pulls)
        print "Assigning key {0} to {1}".format(k, index)
        if index in keys.keys():
            keys[index].append(k.key)
        else:
            keys[index] = [k.key]
    
    
    for i in range(0, threads):
        indices = []
        for d in range(0, time_between_pulls):
            if d % threads == i:
                indices.append(d)
        t = CredentialUpdateThread(indices)
        t.start()
        
