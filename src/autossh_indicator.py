#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Created on 03.05.17 10:50

@author: pavel
"""
import os
import logging

import gi
from gi.repository import Gtk
from locale import gettext as _

log = logging.getLogger(__name__)


try:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3 as appindicator
except:
    import status_icon_adapter as appindicator


class ControlMenu():
    def __init__(self, preferences, active_profiles, sig_handler):
        self.preferences = preferences
        self.active_profiles = active_profiles
        self.sig_handler = sig_handler

        self.profile_items = {}

        self._make_menu_base()
        self._load_profiles()

    def _make_menu_base(self):
        """
        Make unchangeable menu base
        :return: 
        """
        self.menu = Gtk.Menu()

        #self.more_menu = Gtk.Menu()
        #self.more_item = self.__text_menu_item(_("More"))
        #self.more_item.set_submenu(self.more_menu)
        #self.menu.append(self.more_item)

        self.menu.append(Gtk.SeparatorMenuItem())

        options_item = self.__text_menu_item(_("Options"), self.sig_handler.on_menu_options)
        self.menu.append(options_item)

        log_item = self.__text_menu_item(_("Log"), self.sig_handler.on_menu_log)
        self.menu.append(log_item)

        self.menu.append(Gtk.SeparatorMenuItem())

        quit_item = self.__text_menu_item(_("Quit"), self.sig_handler.on_menu_quit)
        self.menu.append(quit_item)

        self.menu.show_all()

    def __text_menu_item(self, item_label, on_activate = None, args = []):
        """
        Create new simple menu item
        :param item_label: text of menu item
        :param on_activate: function to call when item clicked or None 
        :param kwargs: arguments to function        
        :return: new item
        """
        item = Gtk.MenuItem(item_label)

        if on_activate is not None:
            item.set_sensitive(True)
            item.connect("activate", on_activate, *args)

        item.show()
        return item

    def __check_menu_item(self, item_label, checked = False, on_activate = None, args = []):
        """
        Create new checkbox menu item
        :param item_label: text of menu item
        :param checked: should item be checked
        :param on_activate: function to call when item clicked or None         
        :param args: arguments to function    
        
        :return: new item
        """

        item = Gtk.CheckMenuItem(item_label)
        item.set_active(checked)

        if on_activate is not None:
            item.set_sensitive(True)
            item.connect("toggled", on_activate, *args)

        item.show()
        return item

    def __add_menu_item(self, menu, item_id, menu_item):
        """
        Add item to the menu
        :param menu: 
        :param item_id: id of the item
        :param menu_item: 
        :param prepend: Add item to the beginning of the menu 
        :return: 
        """
        self.profile_items[item_id] = (menu_item, menu)
        menu.prepend(menu_item)

    def __remove_menu_item(self, item_id):
        if item_id in self.profile_items:
            item, menu = self.profile_items.pop(item_id)
            menu.remove(item)
            return item

    def _load_profiles(self):
        profiles = [(p.get("id"), p) for (k, p) in self.preferences.list_parameters("ssh_profiles")]

        for id_, profile in sorted(profiles, reverse=True):
            show_in_menu = profile.get("show_in_menu", False)
            # should profile be shown in menu
            if show_in_menu:
                active = id_ in self.active_profiles
                profile_name = profile.get("name")

                item = self.__check_menu_item(profile_name, checked=active,
                                              on_activate=self.sig_handler.on_menu_profile_action,
                                              args=[id_])
                self.__add_menu_item(self.menu, id_, item)

    def reload(self):
        #remove old profiles
        old_profile_ids = list(self.profile_items.keys())
        for id_ in old_profile_ids:
            self.__remove_menu_item(id_)
        #load new
        self._load_profiles()

    def update_active(self):
        for id_ in self.profile_items.keys():
            item, menu = self.profile_items.get(id_)

            active = id_ in self.active_profiles
            actual = item.get_active()

            #change status if needed
            if active != actual:
                #disable signals, change, enable signals
                item.handler_block_by_func(self.sig_handler.on_menu_profile_action)
                item.set_active(active)
                item.handler_unblock_by_func(self.sig_handler.on_menu_profile_action)

    def get_menu(self):
        return self.menu


class TaskbarIndicator:
    INDICATOR_ID = 'autossh'

    def __init__(self, preferences, active_profiles, sig_handler):
        self.preferences = preferences
        self.active_profiles = active_profiles
        self.menu = ControlMenu(preferences, active_profiles, sig_handler)

        self.set_indicator()
        self.set_icons()


    def set_indicator(self):
        self.indicator = appindicator.Indicator.new(TaskbarIndicator.INDICATOR_ID, Gtk.STOCK_INFO,
                                                    appindicator.IndicatorCategory.SYSTEM_SERVICES)
        self.indicator.set_attention_icon(Gtk.STOCK_INFO)
        self.indicator.set_menu(self.menu.get_menu())

    def set_icons(self):
        icon_theme = self.preferences.get("app", "icon_theme")
        theme_path = self.preferences.get("files", "icon_theme_path", icon_theme, string_mode=True)
        theme_path = os.path.abspath(theme_path)

        if os.path.isdir(theme_path):
            self.indicator.set_icon_theme_path(theme_path)

            inactive_icon = self.preferences.get("files", "icons", "inactive")
            active_icon = self.preferences.get("files", "icons", "active")

            if os.path.isfile(os.path.join(theme_path, inactive_icon)):
                self.indicator.set_icon(inactive_icon)

            if os.path.isfile(os.path.join(theme_path, active_icon)):
                self.indicator.set_attention_icon(active_icon)

        else:
            log.info("Not a valid icon theme path %s", theme_path)

    def update(self):
        if len(self.active_profiles) == 0:
            self.indicator.set_status(appindicator.IndicatorStatus.ACTIVE)
        else:
            self.indicator.set_status(appindicator.IndicatorStatus.ATTENTION)

        self.menu.update_active()

    def reload(self):
        self.set_icons()
        self.menu.reload()
        self.update()



