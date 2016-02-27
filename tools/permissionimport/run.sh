#!/bin/bash
. /home/core/bin/activate

cat import.py | paster shell /home/core/src/conf/production.ini



