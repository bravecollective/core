#!/usr/bin/env paster shell conf/production.ini
from brave.core.scripts.update_chars import main
import os
key_update_hours = int(os.environ['CORE_UPDATE_HOURS'])
main(key_update_hours*60)