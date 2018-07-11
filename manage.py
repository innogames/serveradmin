#!/usr/bin/env python3
"""Serveradmin - Django Application Management

Copyright (c) 2018 InnoGames GmbH
"""

import os
import sys

from django.core.management import execute_from_command_line

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'serveradmin.settings')
execute_from_command_line(sys.argv)
