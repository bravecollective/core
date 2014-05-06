#!/usr/bin/env python

import sys
import subprocess

other_branch = None
if len(sys.argv) > 1:
    other_branch = sys.argv[1]
other_branch = (other_branch or
                subprocess.check_output("git config branch.`git rev-parse --abbrev-ref HEAD`.merge",
                                        shell=True) or
                "develop"
               )

subprocess.call("git diff `git merge-base HEAD %s` | flake8 --diff --show-source" % other_branch,
                shell=True)
