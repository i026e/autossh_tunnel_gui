#! /usr/bin/env python3

# -*- coding: utf-8 -*-

"""
Created on Sun Jun 12 08:25:20 2016

@author: pavel
"""
import os
import sys
import json

import time
import signal

import subprocess
import threading
import collections

import logging
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)



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
    log.info("No AppIndicator, using StatusIcon instead")

#translation
import locale
from locale import gettext as _
locale.setlocale(locale.LC_ALL, '')
APP = 'autossh-gui'

if os.path.isdir("./locale"):
    locale.bindtextdomain(APP, "./locale")
locale.textdomain(APP)

#signals
signal.signal(signal.SIGINT, signal.SIG_DFL)  # handle Ctrl-C
signal.signal(signal.SIGHUP, signal.SIG_DFL)
signal.signal(signal.SIGTERM, signal.SIG_DFL)
signal.signal(signal.SIGQUIT, signal.SIG_DFL)

class LogHandler(logging.Handler):
    def __init__(self, buffer_size = 100):
        super(LogHandler, self).__init__()
        self.setFormatter(LogFormatter())
        self.circular_buffer = collections.deque(maxlen = buffer_size)
        self.observers = {}

    def set_buffer_size(self, buffer_size):
        circular_buffer = collections.deque(maxlen = buffer_size)
        for i in range(min(buffer_size, len(self.circular_buffer))):
            #take prev entry and append to the left
            circular_buffer.appendleft(self.circular_buffer.pop())
        self.circular_buffer = circular_buffer

    def emit(self, record):
        msg = self.format(record)

        self.circular_buffer.append(msg)
        self.notify_observers(msg)

    def add_observer(self, obs_name, on_entry_cb):
        self.observers[obs_name] = on_entry_cb

    def delete_observer(self, obs_name):
        if obs_name in self.observers:
            self.observers.pop(obs_name)
            log.info("observer %s unregistered", obs_name)

    def notify_observers(self, msg):
        for observer_cb in self.observers.values():
            observer_cb(msg)

    def history(self):
        return self.circular_buffer

class LogFormatter(logging.Formatter):
    def format(self, record):
        msg = record.msg
        if type(msg) in (list, tuple, set):
            return " ".join(self.get_str(m) for m in msg)


        return self.get_str(msg) % record.args
    def get_str(self, val):
        if isinstance(val, bytes):
            return val.decode("utf-8").strip()
        return str(val).strip()


# decorator for safely update Gtk
def idle_add_decorator(func):
    def callback(*args):
        GObject.idle_add(func, *args)
    return callback


class Preferences:
    CONFIG_FILE = "~/.config/autossh-gui/config.json"
    Default = { "files" : {
                            "glade_file" : "autossh-gui.glade"
                            ,"icon_path" : "./icons"
                            ,"credits_file" : "credits.txt"
                            ,"desktop_file" : "./autossh-gui.desktop"
                            ,"autostart_file" : "~/.config/autostart/autossh-gui.desktop"
                        }, "app" : {
                            "icon_theme" : "light"
                            ,"autostart" : False
                            ,"connect_on_start" : False
                            ,"poll_interval" : 0.1
                            ,"log_keep_entries" : 100
                            ,"log_autoscroll" : False
                        }, "ssh" : {
                            "process" : "autossh"
                            ,"external_addr":"1.2.3.4"
                            ,"external_port":"22"
                            ,"external_user":"user"
                            ,"internal_port":"9999"
                            ,"key_file" :"~/.ssh/id_pub"
                            ,"extra_options" : ["-v -C -N -T", "-o TCPKeepAlive=yes","-o ServerAliveInterval=300"]
                            ,"env_options" : ["AUTOSSH_POLL=30","AUTOSSH_GATETIME=0","AUTOSSH_DEBUG=1","AUTOSSH_PORT=0"]
                        }
                    }



    def __init__(self, conf_file = None):
        conf_file = conf_file if conf_file else Preferences.CONFIG_FILE
        self.conf_file = os.path.expanduser(conf_file)

        self.options = dict((cat, params.copy()) for cat, params in Preferences.Default.items())

        try:
            with open(self.conf_file, "r") as f:
                data = json.loads(f.read())
            for cat, params in data.items():
                if cat in self.options:
                    self.options[cat].update(params)
                else:
                    self.options[cat] = params

        except Exception as e:
            log.exception(e)

    def get(self, cat, name, string_mode=False):
        value = self.options.get(cat, {}).get(name)
        if string_mode:
            return self.as_str(value)

        return value

    def as_str(self, value):
        if value is None:
            return ""

        elif isinstance(value, (list, tuple)):
            return "\n".join(str(elm) for elm in value)

        return str(value)

    def set_raw(self, cat, name, value):
        if cat not in self.options:
            self.options[cat] = {}

        if name not in self.options[cat]:
            self.options[cat][name] = value
        else: # type conversion
            src_type = type(value)
            target_type = type(self.options[cat][name])

            try:
                if (src_type in (str, )) and (target_type in (list, tuple)):
                    lines = value.splitlines()
                    self.options[cat][name] = [line.strip() for line in lines]
                else:
                    self.options[cat][name] = target_type(value)

            except Exception as e:
                    log.info("Error setting property %s: %s", name, e)
                    log.exception(e)

    def list_properties(self):
        for cat, params in self.options.items():
            for name in params.keys():
                yield cat, name

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.conf_file), exist_ok=True)

            diff = {}
            for cat, params in self.options.items():
                diff[cat] = {}
                for key, val in params.items():
                    if Preferences.Default.get(cat, {}).get(key) != val:
                        diff[cat][key] = val

            log.debug("Changed options %s", diff)
            with open(self.conf_file, "w") as f:
                data = json.dumps(diff, indent=4)
                f.write(data)
            log.info("Configuration saved as %s", self.conf_file)

        except Exception as e:
            log.exception(e)
            log.info("Error witing file %s: %s", self.conf_file, e)


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
        log.info("Exec %s", self.command)

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
            log.exception(e)
            on_stop_cb(-1)

    def poll(self, poll_interval, on_stop_cb):
        while True:
            retcode = self.process.poll()
            if retcode is not None: #Process finished
                stdout, stderr = self.process.communicate()
                log.info("stdout: %s", stdout)
                log.info("stderr: %s", stderr)

                on_stop_cb(retcode)
                log.info("return code %s", retcode)

                break
            else:
                log.info(self.process.stdout.readline())

            time.sleep(poll_interval)



    def stop(self):
        self.terminated = True
        if self.process is not None:
            self.process.terminate()
            # Send the signal to all the process groups
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)




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

        icon_path = os.path.abspath(self.preferences.get("files", "icon_path"))
        icon_theme = self.preferences.get("app", "icon_theme")
        self.theme_path = os.path.join(icon_path, icon_theme)

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
            log.info("Icon theme path %s does not exist", self.theme_path)

    def _set_indicator(self):
        raise NotImplementedError

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


class Autostart:
    @staticmethod
    def set_autostart(preferences):
        desktop_file = os.path.expanduser(preferences.get("files", "desktop_file"))
        autostart_file = os.path.expanduser(preferences.get("files", "autostart_file"))
        if preferences.get("app", "autostart"):
            Autostart.enable(desktop_file, autostart_file)
        else:
            Autostart.disable(autostart_file)

    @staticmethod
    def enable(desktop_file, autostart_file):
        if os.path.exists(autostart_file):
            log.info(_("Autostart already enabled"))
            return

        try:
            directory = os.path.dirname(autostart_file)
            subprocess.call(["mkdir", "-p", directory])
            subprocess.call(["cp", desktop_file, autostart_file])
            log.info(_("Autostart enabled"))
        except Exception as e:
            log.info("Problem with copying autostart file: %s", e)
            log.exception(e)

    @staticmethod
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



class GUI_callback:
    def __init__(self, gui, preferences):
        self.gui = gui
        self.preferences = preferences

    def on_button_cancel_clicked(self, *args):
        log.info(_("Settings restored"))
        self.gui.pref_fields_to_window()


    def on_button_ok_clicked(self, *args):
        log.info(_("Settings saved"))
        self.gui.pref_fields_from_window()
        Autostart.set_autostart(self.preferences)

    def on_do_action(self, source):
        self.gui.do_action()

    def on_show_quit(self, source):
        self.gui.quit_(source)

    def on_show_options(self, source):
        self.gui.show_window("options")

    def on_show_log(self, source):
        self.gui.show_window("log")

    def on_autoscroll_checkbox(self, widget):
        state = widget.get_active()
        self.preferences.set_raw("app", "log_autoscroll", state)



class GUI:
    NOTEBOOK_PAGES = {"options": 0, "log":1, "about":2}

    def __init__(self, conf_file = None):
        self.window = None
        self.ssh_client = None

        self.preferences = Preferences(conf_file)
        self.log_handler = LogHandler(self.preferences.get("app","log_keep_entries"))
        log.addHandler(self.log_handler)

        self.callback = GUI_callback(self, self.preferences)

        indicator = APP_Indicator if USE_APPINDICATOR else StatusIcon
        self.indicator = indicator(self.preferences, self.callback)

        Autostart.set_autostart(self.preferences)


    def run(self):
        if self.preferences.get("app", "connect_on_start"):
            self.connect()

        Gtk.main()



    def do_action(self):
        if self.ssh_client is None:
            self.connect()
        else:
            self.disconnect()



    def connect(self):
        if self.ssh_client is None:
            self.ssh_client = AutosshClient(self.preferences.get("ssh","process"),
                                            self.preferences.get("ssh","external_addr"),
                                            self.preferences.get("ssh","external_port"),
                                            self.preferences.get("ssh","external_user"),
                                            self.preferences.get("ssh","internal_port"),
                                            self.preferences.get("ssh","key_file"),
                                            self.preferences.get("ssh","extra_options"),
                                            self.preferences.get("ssh","env_options"))

            self.ssh_client.run(self.preferences.get("app", "poll_interval"),
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
            self.builder.add_from_file(self.preferences.get("files", "glade_file"))
            self.builder.connect_signals(self.callback)

            self.window = self.builder.get_object("window")

            # hide instead of close
            self.window.connect('delete-event', self.hide_window)

            #tabs
            self.notebook = self.builder.get_object("notebook")

            #logging
            self.log_textview = self.builder.get_object("log_textview")
            self.log_buffer = self.log_textview.get_buffer()

            #credits
            self.set_credits()

        self.pref_fields_to_window()

        self.log_buffer.set_text("\n".join(self.log_handler.history()))
        self.log_handler.add_observer("log_textview", self.on_new_log_msg)

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
    def pref_fields_from_window(self):
        for cat, name in self.preferences.list_properties():
            field = self.builder.get_object(cat + "." + name)

            if field is not None:
                read, write, s_mode = self.get_rw_func(field)
                if read is not None:
                    self.preferences.set_raw(cat, name, read())
        self.preferences.save()

    def pref_fields_to_window(self):
        for cat, name in self.preferences.list_properties():
            field = self.builder.get_object(cat + "." + name)

            if field is not None:
                read, write, s_mode = self.get_rw_func(field)
                if write is not None:
                    write(self.preferences.get(cat, name, s_mode))


    def get_rw_func(self, field):
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

        if self.preferences.get("app", "log_autoscroll"):
            self.log_textview.scroll_mark_onscreen(self.log_buffer.get_insert())

    def on_stop_cb(self, code=0):
        log.info("SSH stopped with code %s", code)
        if self.ssh_client is not None:
            self.ssh_client.stop()
            self.ssh_client = None

        self.indicator.mode_inactive()

    def quit_(self, source):
        self.disconnect()
        Gtk.main_quit()


if __name__ == "__main__":
    conf_file = sys.argv[1] if len(sys.argv) >= 2 else None

    GUI(conf_file).run()

