#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Created on 03.05.17 15:59

@author: pavel
"""
import logging

from gi.repository import Gtk

log = logging.getLogger(__name__)
from locale import gettext as _

class TextColumn(Gtk.TreeViewColumn):
    def __init__(self, column_name, tooltip_text, model_index_txt,
                 *args, **kwargs):
        super(TextColumn, self).__init__(*args, **kwargs)

        self.title = Gtk.Label(column_name)
        self.title.set_tooltip_text(tooltip_text)
        self.title.show()
        self.set_widget(self.title)

        renderer_text = Gtk.CellRendererText()
        self.cell_renderers = (renderer_text,)

        self.pack_start(renderer_text, expand=True)
        self.add_attribute(renderer_text, "text", model_index_txt)

        self.set_resizable(True)

    def set_attribute(self, name, model_column):
        for renderer in self.cell_renderers:
            self.add_attribute(renderer, name, model_column)


class FlagColumn(Gtk.TreeViewColumn):
    def __init__(self, column_name, tooltip_text, model_index_bool,
                 on_toggle, *args, on_toggle_data=None, **kwargs):
        super(FlagColumn, self).__init__(*args, **kwargs)

        self.title = Gtk.Label(column_name)
        self.title.set_tooltip_text(tooltip_text)
        self.title.show()
        self.set_widget(self.title)

        renderer_flag = Gtk.CellRendererToggle()
        renderer_flag.set_property("activatable", True)
        self.cell_renderers = (renderer_flag,)

        renderer_flag.connect("toggled", on_toggle, on_toggle_data)

        self.pack_start(renderer_flag, expand=False)
        self.add_attribute(renderer_flag, "active", model_index_bool)

        self.set_clickable(True)
        self.set_resizable(False)

        # self.set_sort_indicator(True)

    def set_attribute(self, name, model_column):
        for renderer in self.cell_renderers:
            self.add_attribute(renderer, name, model_column)


class ProfilesViewModel():
    PROF_ID_COL = 0  # int
    PROF_NAME_COL = 1 # str
    PROF_ACTIVE_COL = 2 # bool

    TOOLTIP_COL = 3 #str

    # id, name, active, tooltip
    LIST_STORE_COLUMN_TYPES = [int, str, bool, str]

    TOOLTIP_TEMPLATE = _("<b>{name}:</b> 127.0.0.1:{loc_port} &lt;-&gt; {serv_addr}:{serv_port}")

    def __init__(self, preferences, active_profiles):
        self.preferences = preferences
        self.active_profiles = active_profiles
        self.list_store = Gtk.ListStore(*self.LIST_STORE_COLUMN_TYPES)

        self.load()


    def get_model(self):
        return self.list_store

    def load(self):
        profiles = [(p.get("id"), p) for (k, p) in self.preferences.list_parameters("ssh_profiles")]
        for id_, profile in sorted(profiles):
            active = id_ in self.active_profiles
            name = profile.get("name")

            tooltip = self.TOOLTIP_TEMPLATE.format(name = name,
                                                    loc_port = profile.get("local_port"),
                                                    serv_addr = profile.get("server_addr"),
                                                    serv_port = profile.get("server_port")
                                                  )

            data = [id_, name, active, tooltip]
            self.list_store.append(data)

    def reload(self):
        self.list_store.clear()
        self.load()

    def set_value(self, path, column, value):
        iter_ = self.list_store.get_iter(path)
        self.list_store.set_value(iter_, column, value)

    def get_value(self, path, column):
        iter_ = self.list_store.get_iter(path)
        return self.list_store.get_value(iter_, column)

    def update_active(self):
        iter_ = self.list_store.get_iter_first()
        while iter_ is not None:
            profile_id = self.list_store.get_value(iter_, self.PROF_ID_COL)
            active = profile_id in self.active_profiles
            self.list_store.set_value(iter_, self.PROF_ACTIVE_COL, active)

            #go to next profile
            iter_ = self.list_store.iter_next(iter_)

    def switch_active(self, path):
        actual = self.get_value(path, self.PROF_ACTIVE_COL)
        log.debug(_("Force toggle %s"), path)

        self.set_value(path, self.PROF_ACTIVE_COL, not actual)

    def get_profile_id(self, path):
        return self.get_value(path, self.PROF_ID_COL)

class ProfilesView:
    def __init__(self, builder, preferences, active_profiles, sig_handler):
        self.sig_handler = sig_handler
        self.view = builder.get_object("ssh_profiles_view")
        self.selection = self.view.get_selection()

        self.model = ProfilesViewModel(preferences, active_profiles)

        self.view.set_model(self.model.get_model())
        self.view.set_tooltip_column(self.model.TOOLTIP_COL)

        active_column = FlagColumn(_("Active"), _("Is connected"),
                                   self.model.PROF_ACTIVE_COL,
                                   self.on_profile_activation)
        name_column = TextColumn(_("Profile name"), _("Profile name"),
                                 self.model.PROF_NAME_COL)
        self.view.append_column(active_column)
        self.view.append_column(name_column)

    def update(self):
        self.model.update_active()

    def reload(self):
        self.model.reload()

    def on_profile_activation(self, widget, path, *args):
        print(widget, path, args)
        profile_id = self.model.get_profile_id(path)

        # UI hack
        self.model.switch_active(path)

        self.sig_handler.on_profile_action(profile_id)
        return True

    def get_selected(self):
        if self.selection.count_selected_rows() >= 1:
            path = self.selection.get_selected_rows()[1][0]

            return self.model.get_profile_id(path)






