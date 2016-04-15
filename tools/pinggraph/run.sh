#!/bin/bash
. /home/core/bin/activate

cat graph.py | paster shell /home/core/src/conf/production.ini
cat graph-t.py | paster shell /home/core/src/conf/production.ini



