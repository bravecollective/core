#!/bin/bash
. /home/core/bin/activate

cat fix_dangleing_key_refrences.py | paster shell /home/core/src/conf/production.ini




