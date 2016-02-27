#!/bin/bash
. /home/core/bin/activate

cat remove.py | paster shell /home/core/src/conf/production.ini



