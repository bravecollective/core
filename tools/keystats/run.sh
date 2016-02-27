#!/bin/bash
. /home/core/bin/activate

cat stats.py | paster shell /home/core/src/conf/production.ini




