#! /usr/bin/env python3

# -*- coding: utf-8 -*-

"""
Created on Sun Jun 12 08:25:20 2016

@author: pavel
"""
import os
import sys

import time
import signal

import subprocess
import threading
import collections


import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import GObject

USE_APPINDICATOR = False
try:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3 as appindicator
    USE_APPINDICATOR = True
except:
    print("No AppIndicator, using StatusIcon instead")

#translation
import locale
from locale import gettext as _
locale.setlocale(locale.LC_ALL, '')
APP = 'autossh-gui'

if os.path.isdir("./locale"):
    locale.bindtextdomain(APP, "./locale")

locale.textdomain(APP)

class Logger(object):
    #singleton
    __instance = None
    def __new__(cls):
        if Logger.__instance is None:
            Logger.__instance = object.__new__(cls)

            Logger.__instance.observers = {}
            Logger.__instance.circular_buffer = collections.deque(maxlen = 100)

        return Logger.__instance

    def add_observer(self, obs_name, on_entry_cb):
        self.observers[obs_name] = on_entry_cb

    def delete_observer(self, obs_name):
        if obs_name in self.observers:
            observer_cb = self.observers.pop(obs_name)
            observer_cb("observer %s unregistered" %obs_name)

    def notify_observers(self, msg):
        for observer_cb in self.observers.values():
            observer_cb(msg)

    def decode(self, val):
        if isinstance(val, bytes):
            val = val.decode("utf-8")

        return str(val)

    def log(self, *args):
        msg = ' '.join(self.decode(a) for a in args)

        self.circular_buffer.append(msg)
        self.notify_observers(msg)

    def set_buffer_size(self, keep_entries):
        circular_buffer = collections.deque(maxlen = keep_entries)
        for i in range(min(keep_entries, len(self.circular_buffer))):
            #take prev entry and append to the left
            circular_buffer.appendleft(self.circular_buffer.pop())
        self.circular_buffer = circular_buffer

# decorator for safely update Gtk
def idle_add_decorator(func):
    def callback(*args):
        GObject.idle_add(func, *args)
    return callback

class DefaultPreferences:
    GUI_GLADE_FILE = "autossh-gui.glade"
    GUI_ICON_PATH = "./icons"
    GUI_ICON_THEME = "light"
    GUI_CREDITS_FILE = "credits.txt"

    CONFIG_FILE = "~/.config/autossh-gui/config.ini"

    CONNECT_ON_START = False

    POLL_INTERVAL = 0.1
    LOG_KEEP_ENTRIES = 100

    SSH_PROCESS = "autossh"
    SSH_EXTERNAL_ADDR = "1.2.3.4"
    SSH_EXTERNAL_PORT = "22"
    SSH_EXTERNAL_USER = "user"
    SSH_INTERNAL_PORT = "9999"
    SSH_KEY_FILE = "~/.ssh/id_pub"

    # -o option
    SSH_EXTRA_OPTIONS = ["-v -C -T",
                         "-o TCPKeepAlive=yes",
                         "-o ServerAliveInterval=300"]

    # export ...
    SSH_ENV_OPTIONS = ["AUTOSSH_POLL=30",
                       "AUTOSSH_GATETIME=0",
                       "AUTOSSH_DEBUG=1",
                       "AUTOSSH_PORT=0"]


class Preferences:
    option_names = {"glade_file":       ("GUI_GLADE_FILE", str),
                    "icon_path":        ("GUI_ICON_PATH", str),
                    "icon_theme":       ("GUI_ICON_THEME", str),
                    "credits_file":     ("GUI_CREDITS_FILE", str),

                    "connect_on_start": ("CONNECT_ON_START", bool),
                    "poll_interval":    ("POLL_INTERVAL", float),
                    "log_keep_entries": ("LOG_KEEP_ENTRIES", int),

                    "ssh_process":       ("SSH_PROCESS", str),
                    "ssh_external_addr": ("SSH_EXTERNAL_ADDR", str),
                    "ssh_external_port": ("SSH_EXTERNAL_PORT", str),
                    "ssh_external_user": ("SSH_EXTERNAL_USER", str),
                    "ssh_internal_port": ("SSH_INTERNAL_PORT", str),

                    "ssh_key_file":         ("SSH_KEY_FILE", str),
                    "ssh_extra_options":    ("SSH_EXTRA_OPTIONS", list),
                    "ssh_env_options":      ("SSH_ENV_OPTIONS", list), }


    def __init__(self, conf_file = None):
        self.conf_file = DefaultPreferences.CONFIG_FILE \
            if conf_file is None else conf_file

        overwritten = self.load_from_file()


        self.options = {}

        for opt_name, (key, _type)  in Preferences.option_names.items():
            value = overwritten.get(key)

            if value is None:
                value = DefaultPreferences.__dict__.get(key)

            elif _type not in (list, tuple):
                try:
                    value = _type(value[-1])
                except ValueError as e:
                    Logger().log("Error reading property {0}: {1}".format(key, e))
                    value = DefaultPreferences.__dict__.get(key)

            self.options[opt_name] = value

    def __getattr__(self, name):
        return self.get(name)

    def get(self, name, string_mode=False):
        if string_mode:
            return self.get_as_str(name)

        return self.options.get(name)


    def get_as_str(self, name):
        value = self.get(name)

        if value is None:
            return ""

        elif isinstance(value, (list, tuple)):
            return "\n".join(str(elm) for elm in value)

        return str(value)

    def set_raw(self, name, value):
        if name not in self.option_names:
            self.options[name] = value

        else: # type conversion
            key, _type = self.option_names[name]

            if _type not in (list, tuple): # option type is not list
                try:
                    self.options[name] = _type(value)
                except ValueError as e:
                    Logger().log("Error setting property {0}: {1}".format(name, e))
            else:
                if isinstance(value, (list, tuple)):
                    self.options[name] = _type(value)
                elif isinstance(value, str):
                    lines = value.splitlines()
                    self.options[name] = [line.strip() for line in lines]
                else:
                    Logger().log("Error setting property {0}: \
                                        cannot convert to list".format(name))


    def load_from_file(self):
        params = {}

        config_path = os.path.expanduser(self.conf_file)

        try:
            with open(config_path, "r") as f:
                for line in f:
                    line = line.strip()

                    if len(line) > 0 and line[0] != "#":
                        equal_sign_ind = line.find("=")
                        if equal_sign_ind > 0:
                            key = line[:equal_sign_ind]
                            value = line[equal_sign_ind+1:]

                            if key not in params:
                                params[key] = []
                            params[key].append(value)
        except (TypeError, IOError) as e:
            print("Error reading file {0}: {1}".format(self.conf_file, e))

        return params
    def save_to_file(self):
        config_path = os.path.expanduser(self.conf_file)

        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)

            with open(config_path, "w") as f:
                for option in Preferences.option_names:
                    key, _type = Preferences.option_names[option]
                    value = self.options.get(option)
                    default_value = DefaultPreferences.__dict__.get(key)

                    if value is not None and value != default_value:
                        if _type not in (list, tuple):
                            value = [value, ]

                        for v in value:
                            f.write("{0}={1}\r\n".format(key, str(v)))

        except (TypeError, IOError) as e:
            print("Error reading file {0}: {1}".format(self.conf_file, e))


class AutosshClient:

    def __init__(self,
                 ssh_process,
                 ssh_external_addr,
                 ssh_external_port,
                 ssh_external_user,
                 ssh_internal_port,
                 ssh_key_file,
                 ssh_extra_options = [],
                 ssh_environ_options = [] ):

        self.process = None

        self.command = [ssh_process,]
        self.command += ["-D", self.escape(ssh_internal_port)]

        self.command += [self.escape(ssh_external_addr)]
        self.command += ["-p", self.escape(ssh_external_port)]
        self.command += ["-l", self.escape(ssh_external_user)]
        self.command += ["-i", self.escape(os.path.expanduser(ssh_key_file))]

        for option in ssh_extra_options:
            self.command += [self.escape(opt) for opt in option.split()]

        self.env = self.get_env(ssh_environ_options)


    def escape(self, val):
        val = str(val).strip()
        #val = val.replace('\"', '\\"')
        #val = '"' + val + '"'

        return val

    def run(self, poll_interval, on_stop_cb):
        #Logger().log(self.env)
        Logger().log(self.command)

        self.terminated = False

        try :
            self.process = subprocess.Popen(self.command,
                                            env=self.env,
                                            stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT,
                                            preexec_fn=os.setsid)


            thr = threading.Thread(target=self.poll,
                             args=(poll_interval, on_stop_cb))
            thr.start()
        except (FileNotFoundError, ) as e:
            Logger().log(e)
            on_stop_cb(-1)

    def poll(self, poll_interval, on_stop_cb):
        while True:
            if self.terminated:
                self.process.terminate()
                #self.process.kill()

                # Send the signal to all the process groups
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)

            retcode = self.process.poll()
            if retcode is not None: #Process finished
                #stdout, stderr = self.process.communicate()
                Logger().log(self.process.communicate())

                on_stop_cb(retcode)
                Logger().log("returned code", retcode)

                break
            else:
                Logger().log(self.process.stdout.readline())

            time.sleep(poll_interval)



    def stop(self):
        self.terminated = True


    def get_env(self, environ_options):
        env = os.environ.copy()

        for opt in environ_options:
            eq_sign = opt.find("=")
            if eq_sign > 0:
                key, val = opt[0:eq_sign], opt[eq_sign+1:]
                env[key] = val

        return env


class ControlMenu():
    def __init__(self, callback):
        self.menu = Gtk.Menu()
        self.items = {}

        self._add_item("status", _("Status"), lbl_pattern=_("Status: {0}"))

        self._add_item("action", _("Action"), on_activate = callback.on_do_action)

        self.menu.append(Gtk.SeparatorMenuItem())

        self._add_item("options", _("Options"), on_activate = callback.on_show_options)
        self._add_item("log", _("Log"), on_activate = callback.on_show_log)

        self.menu.append(Gtk.SeparatorMenuItem())

        self._add_item("quit", _("Quit"), on_activate = callback.on_show_quit)

        self.menu.show_all()

    def _add_item(self, item_name, lbl, on_activate = None, lbl_pattern=None):
        item = Gtk.MenuItem(lbl)

        if on_activate is not None:
            item.connect('activate', on_activate)
        else:
            item.set_sensitive(False)

        self.items[item_name] = (item, lbl_pattern)


        self.menu.append(item)

    def update(self, item_name, text):
        if item_name in self.items:
            (item, lbl_pattern) = self.items[item_name]

            if lbl_pattern is not None:
                text = lbl_pattern.format(text)

            item.set_label(text)

    def show(self, button, time):
        self.menu.popup(None, None, None, None, button, time)


class TaskbarIndicator:
    INDICATOR_ID = 'autossh'
    INDICATOR_ICON = Gtk.STOCK_INFO

    MODES = {"active": {
                 "icon" : "active.svg",
                 "status" : _("Active"),
                 "action" : _("Stop")},
             "inactive" : {
                 "icon" : "inactive.svg",
                 "status" : _("Inactive"),
                 "action" : _("Start")},
             }

    def __init__(self, preferences, callback):
        self.preferences = preferences
        self.menu = ControlMenu(callback)
        self._set_icons()
        self._set_indicator()

        self.mode_inactive()

    def _set_icons(self):
        self.inactive_icon = TaskbarIndicator.INDICATOR_ICON
        self.active_icon = TaskbarIndicator.INDICATOR_ICON

        icon_path = os.path.abspath(self.preferences.icon_path)
        self.theme_path = os.path.join(icon_path, self.preferences.icon_theme)

        if os.path.exists(self.theme_path):
            inactive_icon = os.path.join(self.theme_path,
                                    TaskbarIndicator.MODES["inactive"]["icon"])

            active_icon = os.path.join(self.theme_path,
                                    TaskbarIndicator.MODES["active"]["icon"])

            if os.path.exists(inactive_icon):
                self.inactive_icon = inactive_icon
            if os.path.exists(active_icon):
                self.active_icon = active_icon
        else:
            Logger().log("Icon theme path {0} does not exist".format(theme_path))

    def _set_indicator(self):
        raise notImplemented

    def _set_menu_mode(self, mode):
        if mode in StatusIcon.MODES:
            self.menu.update("status", TaskbarIndicator.MODES[mode]["status"])
            self.menu.update("action", TaskbarIndicator.MODES[mode]["action"])

    def mode_active(self) :
        self._set_menu_mode("active")

    def mode_inactive(self):
        self._set_menu_mode("inactive")


class APP_Indicator(TaskbarIndicator):
    def _set_indicator(self):
        self.indicator = appindicator.Indicator.new(self.INDICATOR_ID,
                                self.INDICATOR_ICON,
                                appindicator.IndicatorCategory.SYSTEM_SERVICES)

        self.indicator.set_menu(self.menu.menu)

        self.indicator.set_icon_theme_path(self.theme_path)

        self.indicator.set_icon(self.inactive_icon)
        self.indicator.set_attention_icon(self.active_icon)

    def mode_active(self) :
        super(APP_Indicator, self).mode_active()
        self.indicator.set_status(appindicator.IndicatorStatus.ATTENTION)

    def mode_inactive(self) :
        super(APP_Indicator, self).mode_inactive()
        self.indicator.set_status(appindicator.IndicatorStatus.ACTIVE)

class StatusIcon(TaskbarIndicator):
    def _set_indicator(self):
        self.indicator = Gtk.StatusIcon()

        #menu on right mouse button
        self.indicator.connect("popup-menu", self.show_menu)

        #left (double)click acts as right click
        self.indicator.connect("activate", lambda *args :
                                self.indicator.emit("popup-menu",
                                0, Gtk.get_current_event_time()))

    def show_menu(self, icon, button, time):
        self.menu.show(button, time)

    def change_icon(self, icon):
        if icon == self.INDICATOR_ICON:
            self.indicator.set_from_stock(icon)
        else:
            self.indicator.set_from_file(icon)

    def mode_active(self) :
        super(StatusIcon, self).mode_active()
        self.change_icon(self.active_icon)

    def mode_inactive(self):
        super(StatusIcon, self).mode_inactive()
        self.change_icon(self.inactive_icon)


class GUI_callback:
    def __init__(self, gui):
        self.gui = gui

    def on_window_hide(self, window, event):
        Logger().delete_observer("log_textview")
        return window.hide() or True

    def on_button_cancel_clicked(self, *args):
        Logger().log(_("Settings restored"))
        self.gui.pref_fields_to_window()
    def on_button_ok_clicked(self, *args):
        Logger().log(_("Settings saved"))
        self.gui.pref_fields_from_window()

    def on_do_action(self, source):
        self.gui.do_action()

    def on_show_quit(self, source):
        self.gui.quit_(source)

    def on_show_options(self, source):
        self.gui.show_window("options")

    def on_show_log(self, source):
        self.gui.show_window("log")



class GUI:
    NOTEBOOK_PAGES = {"options": 0, "log":1, "about":2}

    def __init__(self, conf_file = None):
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        self.window = None

        self.preferences = Preferences(conf_file)
        Logger().set_buffer_size(self.preferences.log_keep_entries)

        self.callback = GUI_callback(self)

        indicator = APP_Indicator if USE_APPINDICATOR else StatusIcon
        self.indicator = indicator(self.preferences, self.callback)

        self.ssh_client = None



    def run(self):
        if self.preferences.connect_on_start:
            self.connect()

        Gtk.main()



    def do_action(self):
        if self.ssh_client is None:
            self.connect()
        else:
            self.disconnect()



    def connect(self):
        if self.ssh_client is None:
            self.ssh_client = AutosshClient(self.preferences.ssh_process,
                                            self.preferences.ssh_external_addr,
                                            self.preferences.ssh_external_port,
                                            self.preferences.ssh_external_user,
                                            self.preferences.ssh_internal_port,
                                            self.preferences.ssh_key_file,
                                            self.preferences.ssh_extra_options,
                                            self.preferences.ssh_env_options)

            self.ssh_client.run(self.preferences.poll_interval,
                                self.on_stop_cb)
        self.indicator.mode_active()

    def disconnect(self):
        if self.ssh_client is not None:
            self.ssh_client.stop()
            self.ssh_client = None
        #self.indicator.mode_inactive()

    def show_window(self, notebook_page):
        if self.window is None:
            self.builder = Gtk.Builder()
            self.builder.set_translation_domain(APP)
            self.builder.add_from_file(self.preferences.glade_file)
            self.builder.connect_signals(self.callback)

            self.window = self.builder.get_object("window")

            # hide instead of close
            self.window.connect('delete-event', self.callback.on_window_hide)

            #tabs
            self.notebook = self.builder.get_object("notebook")

            #logging
            self.log_textview = self.builder.get_object("log_textview")
            self.log_buffer = self.log_textview.get_buffer()

            #credits
            self.set_credits()

        self.pref_fields_to_window()

        self.log_buffer.set_text("".join(Logger().circular_buffer))
        Logger().add_observer("log_textview", self.on_new_log_msg)

        self.window.show_all()
        self.window.present()

        open_page = GUI.NOTEBOOK_PAGES.get(notebook_page, 0)
        self.notebook.set_current_page(open_page)

    def set_credits(self):
        credits_file = self.preferences.credits_file

        try:
            with open(credits_file, "r") as cf:
                credits_view = self.builder.get_object("credits_view")
                credits_buffer = credits_view.get_buffer()
                credits_buffer.set_text(cf.read())
        except (TypeError, IOError) as e:
            Logger().log(e)


    # from
    def pref_fields_from_window(self):
        for option_name in self.preferences.options:
            field = self.builder.get_object(option_name)

            if field is not None:
                read, write, s_mode = self._pref_field_rw_func(field)
                if read is not None:
                    self.preferences.set_raw(option_name, read())
        self.preferences.save_to_file()

    def pref_fields_to_window(self):
        for option_name in self.preferences.options:
            field = self.builder.get_object(option_name)

            if field is not None:
                read, write, s_mode = self._pref_field_rw_func(field)
                if write is not None:
                    write(self.preferences.get(option_name, s_mode))


    def _pref_field_rw_func(self, field):
        # returns:
        # -read function for field
        # -write function for field
        # -string mode
        if isinstance(field, Gtk.Entry):
            return field.get_text, field.set_text, True

        if isinstance(field, Gtk.TextView):
            buffer = field.get_buffer()
            start_iter = buffer.get_start_iter()
            end_iter = buffer.get_end_iter()
            read = lambda buf = buffer, st = start_iter, en = end_iter :\
                buffer.get_text(st, en, True)
            return read, buffer.set_text, True

        if isinstance(field, Gtk.CheckButton):
            return field.get_active, field.set_active, False

        if isinstance(field, Gtk.ComboBox):
            model = field.get_model()
            def read():
                iter_ = field.get_active_iter()
                return model.get_value(iter_, 0)

            def write(value):
                iter_ = model.get_iter_first()
                while iter_ is not None:
                    if model.get_value(iter_, 0) == value:
                        field.set_active_iter(iter_)
                        break
                    iter_ = model.iter_next(iter_)

            return read, write, False



        return None, None, None

    @idle_add_decorator
    def on_new_log_msg(self, msg):
        end_iter = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end_iter, "\n" + msg)

    def on_stop_cb(self, code=0):
        Logger().log("code", code)
        if self.ssh_client is not None:
            self.ssh_client.stop()
            self.ssh_client = None

        self.indicator.mode_inactive()

    def quit_(self, source):
        self.disconnect()
        Gtk.main_quit()


if __name__ == "__main__":
    Logger().add_observer("print", print)

    conf_file = sys.argv[1] if len(sys.argv) >= 2 else None

    GUI(conf_file).run()

