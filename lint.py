#!/usr/bin/env python

from __future__ import print_function

import sys
import subprocess

other_branch = None
if len(sys.argv) > 1:
    other_branch = sys.argv[1]
else:
    try:
        cmd = "git config branch.`git rev-parse --abbrev-ref HEAD`.merge"
        other_branch = subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError:
        print("Defauting to linting against changes since develop", file=sys.stderr)
        other_branch = "develop"

subprocess.call("git diff `git merge-base HEAD %s` | flake8 --diff --show-source" % other_branch,
                shell=True)
