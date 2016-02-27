#!/bin/bash
. /home/core/bin/activate

cat update-alliances.py | paster shell /home/core/src/conf/production.ini
cat update-corporations.py | paster shell /home/core/src/conf/production.ini




