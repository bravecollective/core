from time import sleep
from brave.core.key.model import EVECredential
import random
from threading import Thread
from datetime import datetime, timedelta
from requests.exceptions import HTTPError

class CredentialUpdateThread(Thread):
    def __init__(self, indices, separation):
        super(CredentialUpdateThread, self).__init__()
        self.indices = indices
        self.separation = separation
    
    @property
    def next_index(self):
        for i in self.indices:
            if i > UpdateKeys.current_index:
                return i
        return self.indices[0]
    
    def run(self):
        while True:
            now = datetime.now()
            index = self.next_index
            next_index = now + timedelta(minutes=(self.next_index-UpdateKeys.current_index) if self.next_index > UpdateKeys.current_index else self.separation)
            next_index = next_index - timedelta(microseconds=(next_index.microsecond + next_index.second*1000000))
            sleep((next_index-datetime.now()).total_seconds())
            # There must've been a delay somewhere, recalulate when it's this thread's turn to run
            if not UpdateKeys.current_index + 1 == index and not UpdateKeys.current_index + 1 == index + self.separation:
                continue
            UpdateKeys.current_index = index
            if UpdateKeys.current_index not in UpdateKeys.keys.keys():
                continue
            for k in UpdateKeys.keys[UpdateKeys.current_index]:
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
            
            
class UpdateKeys():
    
    keys = dict()
    # Start at -1 so that the script has time to delegate keys to the threads.
    current_index = -1
    
    @staticmethod
    def main(time_between_pulls=1440, threads=1):
        """ Setting time_between_pulls less than threads will probably cause problems, so don't do it. This script makes
            no guarantee of thread safety, so using more than 1 thread is strongly discouraged if you value your 
            database's integrity."""
        # Seed the keys into a dictionary
        index = 0
        for k in EVECredential.objects():
            print "Assigning key {0} to {1}".format(k.key, index)
            if index in UpdateKeys.keys.keys():
                UpdateKeys.keys[index].append(k.key)
            else:
                UpdateKeys.keys[index] = [k.key]
            index += 1
            
            if index >= time_between_pulls:
                index = 0
    
    
        for i in range(0, threads):
            indices = []
            for d in range(0, time_between_pulls):
                if d % threads == i:
                    indices.append(d)
            t = CredentialUpdateThread(indices, threads)
            t.start()
        
