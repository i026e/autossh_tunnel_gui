#!/usr/bin/env python3
# -*- coding: utf-8 -*-



# We require PyGTK
import gi
from gi.repository import Gtk
from gi.repository import GObject


# We also need os and sys
import os
import sys


# Status
class IndicatorStatus:
    ACTIVE = 0
    ATTENTION = 1

# Types
class IndicatorCategory:
    APPLICATION_STATUS = 0
    SYSTEM_SERVICES = 1

# The main class
class Indicator:
    # Constructor

    def __init__(self, unknown, icon, category):
        # Store the settings
        self.theme_path = ""
        self.inactive_icon = icon
        self.active_icon = ""  # Blank until the user calls set_attention_icon
        self.menu = None  # We have no menu yet

        # Create the status icon
        self.icon = Gtk.StatusIcon()

        # Initialize to the default icon
        self.__draw_icon(self.inactive_icon)

    @staticmethod
    def new(*args, **kwargs):
        return Indicator(*args, **kwargs)

    def set_menu(self, menu):
        # Save a copy of the menu
        self.menu = menu

        # Now attach the icon's signal
        # to the menu so that it becomes displayed
        # whenever the user clicks it
        self.icon.connect("activate", self.show_menu)

        # menu on right mouse button
        self.icon.connect("popup-menu", self.show_menu)

    def set_icon_theme_path(self, path):
        self.theme_path = path

    def set_status(self, status):
        # Status defines whether the active or inactive
        # icon should be displayed.
        if status == IndicatorStatus.ACTIVE:
            self.__draw_icon(self.inactive_icon)
        else:
            self.__draw_icon(self.active_icon)

    def set_icon(self, icon):
        self.inactive_icon = icon
        self.__draw_icon(self.inactive_icon)

    def set_attention_icon(self, icon):
        # Set the icon filename as the attention icon
        self.active_icon = icon

    def show_menu(self, *args):
        # Show the menu
        self.menu.popup(None, None, None, 0, 0, Gtk.get_current_event_time())


    def check_mouse(self):
        if not self.menu.get_window().is_visible():
            return

        return True


    def hide_menu(self):
        self.menu.popdown()

    def __draw_icon(self, icon):
        icon_path = os.path.join(self.theme_path, icon)
        if os.path.isfile(icon_path):
            self.icon.set_from_file(icon_path)
        else:
            self.icon.set_from_stock(icon)
