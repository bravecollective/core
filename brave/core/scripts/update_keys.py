import random

from collections import defaultdict
from datetime import datetime, timedelta
from math import ceil
from mutex import mutex
from time import sleep
from threading import Lock, Thread
from requests.exceptions import HTTPError

from brave.core.key.model import EVECredential

keys_by_timeslot = defaultdict(list)
keys_lock = Lock()

class CredentialUpdateThread(Thread):
    def __init__(self, key_group_indexes, start_time, interval):
        super(CredentialUpdateThread, self).__init__()
        self.key_group_indexes = key_group_indexes
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
            
            # grab a copy of the list of keys to update
            with keys_lock:
                keys_to_update = keys_by_timeslot[self.key_group_indexes[self.group]]
            
            # do the update
            for k in keys_to_update:
                self.update_key(k)
            
            # update for the next pass
            self.group = (self.group + 1) % len(self.key_group_indexes)
            self.wake_time += self.interval
    
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

def refresh_keylist(num_timeslots):
    global keys_by_timeslot
    
    with keys_lock:
        keys_by_timeslot = defaultdict(list)
        
        for k in EVECredential.objects():
            index = hash(k.id) % num_timeslots
            print "Assigning key {0} to timeslot {1}".format(k.key, index)
            keys_by_timeslot[index].append(k.key)

def main(minutes_between_pulls=1440, threads=1):
    """
    minutes_between_pulls will be rounded up to a multiple of threads. A batch of keys will be
    pulled every minute, so minutes_between_pulls is also the number of batches, and each thread
    will begin a batch once every `threads` minutes.
    """
    
    # round up to a multiple of threads
    minutes_between_pulls = int(ceil(float(minutes_between_pulls) / threads) * threads)
    
    refresh_keylist(num_timeslots=minutes_between_pulls)
    
    first_start_time = datetime.now() + timedelta(seconds=5)
    interval = timedelta(minutes=threads)
    for i in range(0, threads):
        key_group_indexes = list(range(i, minutes_between_pulls, threads))
        start_time = first_start_time+timedelta(minutes=i)
        t = CredentialUpdateThread(key_group_indexes, start_time=start_time, interval=interval)
        t.daemon = True
        t.start()
    
    # Once every minutes_between_pulls, update the list of keys to pull
    wake_time = datetime.now() + timedelta(minutes=minutes_between_pulls)
    while True:
        while datetime.now() < wake_time:
            sleep((wake_time - datetime.now()).total_seconds())
        
        print "refreshing keylist"
        refresh_keylist(num_timeslots=minutes_between_pulls)
        
        wake_time += timedelta(minutes=minutes_between_pulls)
