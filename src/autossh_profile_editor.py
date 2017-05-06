#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Created on 05.05.17 11:02

@author: pavel
"""
import gui_utils as utils

class ProfileEditor:
    #keep max ssh profile id between different editors
    max_profile_id = -1

    def __init__(self, builder, preferences, sig_handler):
        self.builder = builder
        self.preferences = preferences
        self.sig_handler = sig_handler

        self.ssh_profile = None

        self.builder.add_from_file(self.preferences.get("files", "editor_glade_file"))
        self.window = self.builder.get_object("editor_window")
        self.window.connect("delete-event", self._on_quit)

        ok_button = self.builder.get_object("editor_ok")
        cancel_button = self.builder.get_object("editor_cancel")
        ok_button.connect("clicked", self._on_apply)
        cancel_button.connect("clicked", self._on_quit)

        self.name = self.builder.get_object("ssh.name")
        self.serv_addr = self.builder.get_object("ssh.server_addr")
        self.serv_port = self.builder.get_object("ssh.server_port")
        self.local_port = self.builder.get_object("ssh.local_port")
        self.serv_user = self.builder.get_object("ssh.server_user")
        self.key_file = self.builder.get_object("ssh.key_file")

        self.show_in_menu  = self.builder.get_object("ssh.show_in_menu")
        self.autostart = self.builder.get_object("ssh.autostart")

        self.extra_options = self.builder.get_object("ssh.extra_options")
        self.env_options = self.builder.get_object("ssh.env_options")



    def preferences_from_window(self, ssh_profile):
        ssh_profile["name"] = self.name.get_text()
        ssh_profile["server_addr"] = self.serv_addr.get_text()
        ssh_profile["server_port"] =self.serv_port.get_text()
        ssh_profile["local_port"] = self.local_port.get_text()
        ssh_profile["server_user"] = self.serv_user.get_text()
        ssh_profile["key_file"] = self.key_file.get_text()

        ssh_profile["show_in_menu"] = self.show_in_menu.get_active()
        ssh_profile["autostart"] = self.autostart.get_active()

        ssh_profile["extra_options"] = utils.read_textview(self.extra_options)
        ssh_profile["env_options"] = utils.read_textview(self.env_options)

        return ssh_profile

    def preferences_to_window(self, ssh_profile):
        self.name.set_text(ssh_profile.get("name"))
        self.serv_addr.set_text(ssh_profile.get("server_addr"))
        self.serv_port.set_text(ssh_profile.get("server_port"))
        self.local_port.set_text(ssh_profile.get("local_port"))
        self.serv_user.set_text(ssh_profile.get("server_user"))
        self.key_file.set_text(ssh_profile.get("key_file"))

        self.show_in_menu.set_active(ssh_profile.get("show_in_menu", False))
        self.autostart.set_active(ssh_profile.get("autostart", False))

        utils.write_textview(self.extra_options, ssh_profile.get("extra_options", []))
        utils.write_textview(self.env_options, ssh_profile.get("env_options", []))


    def show(self):
        self.window.show()

    def create(self):
        self.ssh_profile_id, self.ssh_profile = self.new_profile()
        self.preferences_to_window(self.ssh_profile)
        self.window.show()

    def edit(self, profile_id):
        self.ssh_profile_id = profile_id
        self.ssh_profile =  self.preferences.get("ssh_profiles", profile_id)

        self.preferences_to_window(self.ssh_profile)
        self.window.show()

    def _on_apply(self, *args):
        self.preferences_from_window(self.ssh_profile)
        self.preferences.set_raw(self.ssh_profile, "ssh_profiles", self.ssh_profile_id)

        self.sig_handler.on_profile_edited(self.ssh_profile_id)

        self._on_quit(*args)

    def _on_quit(self, *args):
        self.window.destroy()
        return True #!!!

    def new_profile(self):
        if ProfileEditor.max_profile_id < 0:
            profile_ids = [p.get("id") for (k, p) in self.preferences.list_parameters("ssh_profiles")]
            # may be empty, so append 0
            ProfileEditor.max_profile_id = max(profile_ids + [0])

        ProfileEditor.max_profile_id += 1
        profile_templ = self.preferences.get_copy("ssh_profile_template")

        profile_templ["id"] = ProfileEditor.max_profile_id
        profile_templ["name"] =  profile_templ["name"].format(ProfileEditor.max_profile_id)

        return ProfileEditor.max_profile_id, profile_templ
