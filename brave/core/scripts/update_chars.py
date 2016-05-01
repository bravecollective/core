# update_characters.py
import random

from collections import defaultdict
from datetime import datetime, timedelta
from math import ceil
from mutex import mutex
from time import sleep
from threading import Lock, Thread
from requests.exceptions import HTTPError

from brave.core.character.model import EVECharacter

chars_by_timeslot = defaultdict(list)
chars_lock = Lock()

class CredentialUpdateThread(Thread):
    def __init__(self, char_group_indexes, start_time, interval):
        super(CredentialUpdateThread, self).__init__()
        self.char_group_indexes = char_group_indexes
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
            
            # grab a copy of the list of chars to update
            with chars_lock:
                chars_to_update = chars_by_timeslot[self.char_group_indexes[self.group]]
            
            print "Updating {0} chars for this timeslot...".format(len(chars_to_update))

            # do the update
            for n in chars_to_update:
                self.update_character(n)
            
            # update for the next pass
            self.group = (self.group + 1) % len(self.char_group_indexes)
            self.wake_time += self.interval
    
    @staticmethod
    def update_character(n):

        # refresh char
        char = EVECharacter.objects(name=n).first()

        if not char:
            print "Char {0} not found".format(n)
            return

        char_result = None
        try:
            print "Pulling char {0}".format(n)
            char_result = char.pull_character(name=n)
        except HTTPError as e:
            print("Error {0}: {1}".format(e.response.status_code, e.response.text))
        except Exception as ex:
            char_result = False
            print("Error {0}".format(ex))
            
        if char_result is None:
            print("Removed disabled char {0} from account {1} with characters {2}".format(n, char.owner, char.characters))

def refresh_charlist(num_timeslots):
    global chars_by_timeslot
    
    with chars_lock:
        chars_by_timeslot = defaultdict(list)
        
        print "Assigning chars to timeslots - starting..."
        for n in EVECharacter.objects():
            index = hash(n.id) % num_timeslots
            #print "Assigning char {0} to timeslot {1}".format(n.name, index)
            chars_by_timeslot[index].append(n.name)

        print "Assigning chars to timeslots - done!"

def main(minutes_between_pulls=1440, threads=1):
    """
    minutes_between_pulls will be rounded up to a multiple of threads. A batch of chars will be
    pulled every minute, so minutes_between_pulls is also the number of batches, and each thread
    will begin a batch once every `threads` minutes.
    """
    
    # round up to a multiple of threads
    minutes_between_pulls = int(ceil(float(minutes_between_pulls) / threads) * threads)
    
    refresh_charlist(num_timeslots=minutes_between_pulls)
    
    first_start_time = datetime.now() + timedelta(seconds=5)
    interval = timedelta(minutes=threads)
    for i in range(0, threads):
        char_group_indexes = list(range(i, minutes_between_pulls, threads))
        start_time = first_start_time+timedelta(minutes=i)
        t = CredentialUpdateThread(char_group_indexes, start_time=start_time, interval=interval)
        t.daemon = True
        t.start()
    
    # Once every minutes_between_pulls, update the list of charss to pull
    wake_time = datetime.now() + timedelta(minutes=minutes_between_pulls)
    while True:
        while datetime.now() < wake_time:
            sleep((wake_time - datetime.now()).total_seconds())
        
        print "refreshing charlist - start"
        refresh_charlist(num_timeslots=minutes_between_pulls)
        print "refreshing charlist - done"

        wake_time += timedelta(minutes=minutes_between_pulls)
