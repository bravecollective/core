from __future__ import absolute_import, print_function, unicode_literals

import sys
from brave.core import core_loadapp
if __name__ == "__main__":
    core_loadapp("config:"+sys.argv[1] if len(sys.argv) > 1 else None)

import time

from requests.exceptions import HTTPError

from brave.core.key.model import EVECredential
from brave.core.util.signal import validate_key

for k in EVECredential.objects():
    print("refreshing key {}".format(k.id))
    id = k.id
    try:
        k = k.pull()
    except HTTPError as e:
        print("Error {}: {}".format(e.response.status_code, e.response.text))
    if not k:
        print("removed a disabled key")

    # Guarantee that we make a max of 10 QPS to CCP due to this refresh process. Actual QPS will be
    # much lower (due to time spent actually making the calls).
    time.sleep(0.1)

for c in EVECharacter.objects():
    print("checking character {}".format(c))
    if c.credentials == []:
        print("deleting character without keys")
        c.delete()
