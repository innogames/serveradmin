#!/usr/bin/env python
"""Serveradmin - adminapi - Convenience script for testing

Copyright (c) 2018 InnoGames GmbH
"""
# NOTE: This binary is provided for convenience.  It is nice to be able to run
# the checks from the repository.  This is not included on the releases.  We
# are using entry_points mechanism on the setup.py.

from adminapi.cli import main

main()
