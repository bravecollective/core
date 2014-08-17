from time import sleep
from brave.core.key.model import EVECredential
import random
from threading import Thread
from datetime import datetime, timedelta
from requests.exceptions import HTTPError

class CredentialUpdateThread(Thread):
    def __init__(self, key_groups, start_time, interval):
        super(CredentialUpdateThread, self).__init__()
        self.key_groups = key_groups
        self.wake_time = start_time
        self.interval = interval
        self.group = 0
    
    def run(self):
        while True:
            if datetime.now() > self.wake_time:
                print "warning: no delay between groups! Likely falling behind requested time between pulls."
            
            # wait for the next wake time to arrive
            while datetime.now() < self.wake_time:
                sleep((self.wake_time - datetime.now()).total_seconds())
            
            # process the next batch of keys
            for k in self.key_groups[self.group]:
                self.update_key(k)
            
            # update for the next pass
            self.group = (self.group + 1) % len(self.key_groups)
            self.wake_time = self.wake_time + self.interval
    
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
            
            
def main(minutes_between_pulls=1440, threads=1):
    """
    minutes_between_pulls will be rounded up to a multiple of threads. A batch of keys will be
    pulled every minute, so minutes_between_pulls is also the number of batches, and each thread
    will begin a batch once every `threads` minutes.
    """
    
    # round up to a multiple of threads
    minutes_between_pulls = (minutes_between_pulls + threads - 1) % threads
    
    keys_by_timeslot = defaultdict(list)
    
    for i, k in enumerate(EVECredential.objects()):
        index = i % minutes_between_pulls
        print "Assigning key {0} to timeslot {1}".format(k.key, index)
        keys_by_timeslot[index].append(k.key)
    
    first_start_time = datetime.now() + timedelta(seconds=5)
    interval = timedelta(minutes=threads)
    for i in range(0, threads):
        key_groups = list(keys_by_timeslot[i] for i in range(i, minutes_between_pulls, threads))
        start_time = first_start_time+timedelta(minutes=i)
        t = CredentialUpdateThread(key_groups, start_time=start_time, interval=interval)
        t.start()
