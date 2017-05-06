#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Created on 03.05.17 12:24

@author: pavel
"""
import os
import json
from copy import deepcopy

#logging
import logging
log = logging.getLogger(__name__)

#locale
import locale
locale.setlocale(locale.LC_ALL, '')
APP = 'autossh-gui'
if os.path.isdir("../locale"):
    locale.bindtextdomain(APP, "../locale")
locale.textdomain(APP)
from locale import gettext as _


CONFIG_FILE = "~/.config/autossh-gui/config.json"
DEFAULT = { "files" : {
                            "main_glade_file" : "autossh-gui.glade"
                            ,"editor_glade_file" : "autossh-editor.glade"
                            ,"credits_file" : "./files/credits.txt"

                            ,"desktop_file" : "./files/autossh-gui.desktop"
                            ,"autostart_file" : "~/.config/autostart/autossh-gui.desktop"

                            ,"icon_theme_path" : { "light" : "./icons/light/",
                                                   "dark" : "./icons/dark/"  }
                            ,"icons" : {"active" : "active.svg",
                                        "inactive" : "inactive.svg"}
            }, "app" : {
                            "icon_theme" : "light"
                            ,"autostart" : False
                            ,"poll_interval" : 0.1
                            ,"log_keep_entries" : 100
                            ,"log_autoscroll" : False
            }, "ssh_profile_template" :{
                            "id" : 0
                            ,"name" : "SSH Profile {0}"
                            ,"autostart" : False
                            ,"show_in_menu" : True
                            ,"executable" : "autossh"
                            ,"server_addr":"1.2.3.4"
                            ,"server_port":"22"
                            ,"server_user":"user"
                            ,"local_port":"9999"
                            ,"key_file" :"~/.ssh/id_pub"
                            ,"extra_options" : ["-v -C -N -T", "-o TCPKeepAlive=yes","-o ServerAliveInterval=300"]
                            ,"env_options" : ["AUTOSSH_POLL=30","AUTOSSH_GATETIME=0","AUTOSSH_DEBUG=1","AUTOSSH_PORT=0"]

            },  "ssh_profiles" : {}

            }



class Preferences:
    def __init__(self, conf_file = None):
        conf_file = conf_file if conf_file else CONFIG_FILE
        self.conf_file = os.path.expanduser(conf_file)

        self.options = deepcopy(DEFAULT)

        try:
            log.debug("Open %s", self.conf_file)
            with open(self.conf_file, "r") as f:
                data = json.loads(f.read())
            for cat, params in data.items():
                if cat in self.options:
                    self.options[cat].update(params)
                else:
                    self.options[cat] = params

        except Exception as e:
            log.info("Problem reading preference file %s", str(e))
            log.exception(e)

    def list_parameters(self, *path):
        """    
        :param path: path       
        :returns: list of (key, parameter) for given path or None
        """
        node = self.options

        for branch in path:
            # json keeps parameter names as string
            branch = str(branch)
            if branch not in node:
                log.debug("No such path %s", path)
                return
            node = node[branch]

        return list(node.items())


    def remove(self, *path):
        """
        removes last element in the path
        :param path: path to the element
        :return: element or None
        """
        log.debug("Removing %s", path)
        # json keeps parameter names as string
        name = str(path[-1])
        node = self.options

        for branch in path[:-1]:
            # json keeps parameter names as string
            branch = str(branch)
            if branch not in node:
                log.debug("No such path %s", path)
                return
            node = node[branch]

        if name in node:
            return node.pop(name)

    def get(self, *path, string_mode=False):
        """        
        :param path: path to the value
        :param string_mode: should value be converted to string
        :return: value or None
        """
        node = self.options
        for branch in path:
            #json keeps parameter names as string
            branch = str(branch)
            if branch in node:
                node = node[branch]
            else:
                log.debug("No such path %s", path)
                return None

        if string_mode:
            return self.__as_str(node)
        return node

    def get_copy(self, *path):
        """        
        :param path: path to the object
        :return: copy of the object
        """
        return deepcopy(self.get(*path))

    def __as_str(self, value):
        if value is None:
            return ""

        elif isinstance(value, (list, tuple)):
            return "\n".join(str(elm) for elm in value)

        return str(value)

    def __convert_type(self, value, src_type, target_type):
        """May throw an error"""
        if (src_type in (str,)) and (target_type in (list, tuple)):
            lines = value.splitlines()
            return [line.strip() for line in lines]
        else:
            return target_type(value)

    def set_raw(self, value, *path):
        try:
            # json keeps parameter names as string
            name = str(path[-1])
            node = self.options

            for branch in path[:-1]:
                # json keeps parameter names as string
                branch = str(branch)
                if branch not in node:
                    node[branch] = {}
                node = node[branch]

            if name not in node:
                node[name] = value
            else: # type conversion
                src_type = type(value)
                target_type = type(node[name])

                node[name] = self.__convert_type(value, src_type, target_type)

        except Exception as e:
            log.info("Error setting property %s: %s", name, e)
            log.exception(e)
    """
    def list_properties(self):
        for cat, params in self.options.items():
            for name in params.keys():
                yield cat, name
    """

    def save(self):
        log.debug("Writing file %s", self.conf_file)
        try:
            os.makedirs(os.path.dirname(self.conf_file), exist_ok=True)

            with open(self.conf_file, "w") as f:
                data = json.dumps(self.options, indent=4)
                f.write(data)
            log.info("Configuration saved as %s", self.conf_file)

        except Exception as e:
            log.exception(e)
            log.info("Error witing file %s: %s", self.conf_file, e)

