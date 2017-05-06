#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Created on 06.05.17 10:45

@author: pavel
"""

import os
from locale import gettext as _

import logging
log = logging.getLogger(__name__)

from subprocess import call


def set_autostart(preferences):
    desktop_file = os.path.expanduser(preferences.get("files", "desktop_file"))
    autostart_file = os.path.expanduser(preferences.get("files", "autostart_file"))
    if preferences.get("app", "autostart"):
        enable(desktop_file, autostart_file)
    else:
        disable(autostart_file)


def enable(desktop_file, autostart_file):
    if os.path.exists(autostart_file):
        log.info(_("Autostart already enabled"))
        return

    try:
        directory = os.path.dirname(autostart_file)
        call(["mkdir", "-p", directory])
        call(["cp", desktop_file, autostart_file])
        log.info(_("Autostart enabled"))
    except Exception as e:
        log.info("Problem with copying autostart file: %s", e)
        log.exception(e)


def disable(autostart_file):
    if not os.path.exists(autostart_file):
        log.info(_("Autostart already disabled"))
        return

    try:
        os.remove(autostart_file)
        log.info(_("Autostart disbled"))
    except Exception as e:
        log.info("Problem with deleting autostart file: %s", e)
        log.exception(e)

