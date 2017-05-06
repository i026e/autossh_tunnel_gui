#! /usr/bin/env python3

# -*- coding: utf-8 -*-

"""
Created on Sun Jun 12 08:25:20 2016

@author: pavel
"""
import sys

#signals
import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)  # handle Ctrl-C
signal.signal(signal.SIGHUP, signal.SIG_DFL)
signal.signal(signal.SIGTERM, signal.SIG_DFL)
signal.signal(signal.SIGQUIT, signal.SIG_DFL)

#gtk
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

import gui_utils as utils
import autossh_preferences
import app_autostart

from autossh_log import LimLogHandler
from autossh_client import AutosshClient
from autossh_indicator import TaskbarIndicator
from autossh_profile_view import ProfilesView
from autossh_profile_editor import ProfileEditor

from locale import gettext as _

#logger
import logging
log = logging.getLogger(__name__)

class GUI:
    NOTEBOOK_PAGES = {"options": 0, "log":1, "about":2}

    def __init__(self, conf_file = None):
        self.window = None
        self.profiles_view = None
        self.profile_editor = None
        self.active_profiles = {}

        self.preferences = autossh_preferences.Preferences(conf_file)
        self.log_handler = LimLogHandler(self.preferences.get("app","log_keep_entries"))


        self.sig_handler = self
        self.indicator = TaskbarIndicator(self.preferences, self.active_profiles, sig_handler = self)

        app_autostart.set_autostart(self.preferences)


    def run(self):
        #if self.preferences.get("app", "connect_on_start"):
        #    self.connect()

        Gtk.main()

    def connect(self, profile_id):
        log.debug(_("Connecting %s"), profile_id)

        if profile_id not in self.active_profiles:
            ssh_profile = self.preferences.get("ssh_profiles", profile_id)
            if ssh_profile is not None:
                ssh_client = AutosshClient(self.preferences, ssh_profile)
                self.active_profiles[profile_id] = ssh_client
                ssh_client.run(self.preferences.get("app", "poll_interval"), self.on_ssh_stop)
            else:
                log.error(_("No SSH profile with id %s"), profile_id)

        self.update()

    def disconnect(self, profile_id):
        """
        Safely disconnect
        :param profile_id: 
        :return: 
        """
        log.debug(_("Disconnecting %s"), profile_id)
        if profile_id in self.active_profiles:
            ssh_client = self.active_profiles[profile_id]
            ssh_client.stop()
        else:
            log.error(_("No active SSH profile with id %s"), profile_id)



    def show_window(self, notebook_page):
        if self.window is None:
            self.builder = Gtk.Builder()
            self.builder.set_translation_domain(autossh_preferences.APP)
            self.builder.add_from_file(self.preferences.get("files", "main_glade_file"))
            self.builder.connect_signals(self)

            self.window = self.builder.get_object("window")

            # hide instead of close
            self.window.connect('delete-event', self.hide_window)

            #tabs
            self.notebook = self.builder.get_object("notebook")

            #preferences
            self.profiles_view = ProfilesView(self.builder, self.preferences, self.active_profiles,
                                              sig_handler=self)

            #logging
            self.log_textview = self.builder.get_object("log_textview")
            self.log_buffer = self.log_textview.get_buffer()

            #credits
            self.set_credits()

        self.preferences_to_window()

        self.log_buffer.set_text("\n".join(self.log_handler.history()))
        self.log_handler.add_observer("log_textview", self.add_log_message)

        self.window.show_all()
        self.window.present()

        open_page = GUI.NOTEBOOK_PAGES.get(notebook_page, 0)
        self.notebook.set_current_page(open_page)

    def hide_window(self, *args):
        if self.window:
            self.window.hide()
        return True

    def set_credits(self):
        credits_file = self.preferences.get("files", "credits_file")

        try:
            with open(credits_file, "r") as cf:
                credits_view = self.builder.get_object("credits_view")
                credits_buffer = credits_view.get_buffer()
                credits_buffer.set_text(cf.read())
        except (TypeError, IOError) as e:
            log.exception(e)

    # from
    def preferences_from_window(self):
        autostart = self.builder.get_object("app.autostart")
        self.preferences.set_raw(autostart.get_active(), "app", "autostart")

        log_autoscroll = self.builder.get_object("app.log_autoscroll")
        self.preferences.set_raw(log_autoscroll.get_active(), "app", "log_autoscroll")

        icon_theme_box = self.builder.get_object("app.icon_theme")
        self.preferences.set_raw(utils.read_iterable(icon_theme_box), "app", "icon_theme")


        self.preferences.save()

    def preferences_to_window(self):
        autostart = self.builder.get_object("app.autostart")
        autostart.set_active(self.preferences.get("app", "autostart"))

        log_autoscroll = self.builder.get_object("app.log_autoscroll")
        log_autoscroll.set_active(self.preferences.get("app", "log_autoscroll"))

        icon_theme_box = self.builder.get_object("app.icon_theme")
        utils.write_iterable(icon_theme_box, self.preferences.get("app", "icon_theme"))

    def remove_profile(self, profile_id):
        self.disconnect(profile_id)
        self.preferences.remove("ssh_profiles", profile_id)

        self.reload()

    @utils.idle_add_decorator
    def update(self):
        log.debug("GUI Update")
        self.indicator.update()
        if self.profiles_view is not None:
            self.profiles_view.update()

    @utils.idle_add_decorator
    def reload(self):
        """ More drastical update"""
        log.debug("GUI Reload")
        self.indicator.reload()
        if self.profiles_view is not None:
            self.profiles_view.reload()


    def quit_(self, *args):
        log.debug(_("Quit"))
        active_ids = self.active_profiles.keys()
        for id in active_ids:
            self.disconnect(id)

        self.preferences.save()
        Gtk.main_quit()

    #signals
    @utils.idle_add_decorator
    def add_log_message(self, msg):
        end_iter = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end_iter, "\n" + msg)

        if self.preferences.get("app", "log_autoscroll"):
            self.log_textview.scroll_mark_onscreen(self.log_buffer.get_insert())

    def on_ssh_stop(self, profile_id, code=0):
        name = self.preferences.get("ssh_profiles", profile_id, "name", string_mode=True)
        log.info(_("SSH %s has stopped"), name, code)
        log.info(_("return code"), code)

        if profile_id in self.active_profiles:
            self.active_profiles.pop(profile_id)
        self.update()

    def on_button_add_clicked(self, *args):
        log.debug(_("Adding new profile"))

        profile_editor = ProfileEditor(self.builder, self.preferences, sig_handler=self)
        profile_editor.create()

    def on_button_delete_clicked(self, *args):
        profile_id = self.profiles_view.get_selected()
        log.debug(_("Deleting profile %s"), profile_id)

        if profile_id is not None:
            name = self.preferences.get("ssh_profiles", profile_id, "name", string_mode=True)
            if utils.get_confirmation(self.window, _("Are you sure to delete profile '{0}'?").format(name)):
                self.remove_profile(profile_id)
        else:
            log.debug(_("No such profile %s"), profile_id)

    def on_button_edit_clicked(self, *args):
        profile_id = self.profiles_view.get_selected()
        log.debug(_("Editing profile %s"), profile_id)
        if profile_id is not None:
            profile_editor = ProfileEditor(self.builder, self.preferences, sig_handler=self)
            profile_editor.edit(profile_id)
        else:
            log.debug(_("No such profile %s"), profile_id)


    def on_button_ok_clicked(self, *args):
        log.debug(_("Saving settings"))
        self.preferences_from_window()
        self.reload()

        app_autostart.set_autostart(self.preferences)

    def on_profile_action(self, profile_id):
        if profile_id in self.active_profiles:
            self.disconnect(profile_id)
        else:
            self.connect(profile_id)

    def on_menu_profile_action(self, source, profile_id):
        if profile_id in self.active_profiles:
            self.disconnect(profile_id)
        else:
            self.connect(profile_id)

    def on_menu_quit(self, source):
        self.quit_(source)

    def on_menu_options(self, source):
        self.show_window("options")

    def on_menu_log(self, source):
        self.show_window("log")

    def on_log_autoscroll_toggled(self, widget):
        log.debug(_("Log autoscroll toggled"))
        state = widget.get_active()
        self.preferences.set_raw("app", "log_autoscroll", state)

    def on_profile_edited(self, profile_id):
        self.reload()


if __name__ == "__main__":
    conf_file = sys.argv[1] if len(sys.argv) >= 2 else None

    GUI(conf_file).run()

