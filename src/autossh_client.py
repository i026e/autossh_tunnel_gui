#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Created on 03.05.17 10:25

@author: pavel
"""
import os
import subprocess

import signal
import logging

from threading import Thread
from time import sleep

log = logging.getLogger(__name__)

class AutosshClient:

    def __init__(self, preferences, ssh_profile):
        self.process = None
        self.preferences = preferences

        self.prof_id = ssh_profile.get("id", 0)
        self.prof_name = ssh_profile.get("name")

        executable = self.escape(ssh_profile.get("executable"))

        server_addr = self.escape(ssh_profile.get("server_addr"))
        server_port = self.escape(ssh_profile.get("server_port"))
        server_user = self.escape(ssh_profile.get("server_user"))
        local_port = self.escape(ssh_profile.get("local_port"))
        key_file = self.escape(os.path.expanduser(ssh_profile.get("key_file")))

        extra_options = ssh_profile.get("extra_options")
        env_options = ssh_profile.get("env_options")

        self.command = [executable,]
        self.command += ["-D", local_port]

        self.command += [server_addr]
        self.command += ["-p", server_port]
        self.command += ["-l", server_user]
        self.command += ["-i", key_file]

        for option in extra_options:
            self.command += [self.escape(opt) for opt in option.split()]

        self.env = self.get_env(env_options)


    def escape(self, val):
        val = str(val).strip()
        #val = val.replace('\"', '\\"')
        #val = '"' + val + '"'

        return val

    def run(self, poll_interval, on_stop_cb):
        #Logger().log(self.env)
        log.info("%s: %s", self.prof_name, self.command)

        try :
            thr = Thread(target=self.background,
                             args=(poll_interval, on_stop_cb))
            thr.start()
        except Exception as e:
            log.exception(e)
            log.info("%s:unexpected error: %s", self.prof_name, str(e))
            on_stop_cb(self.prof_id, -1)


    def background(self, poll_interval, on_stop_cb):
        retcode = None


        try:
            # start
            self.process = subprocess.Popen(self.command,
                                            env=self.env,
                                            stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT,
                                            preexec_fn=os.setsid)

            # poll
            while self.process.poll() is None:
                log.info("%s: %s", self.prof_name, self.process.stdout.readline())
                sleep(poll_interval)

            # stop
            stdout, stderr = self.process.communicate(timeout=poll_interval)
            log.info("%s:stdout: %s", self.prof_name, stdout)
            log.info("%s:stderr: %s", self.prof_name, stderr)

            retcode = self.process.returncode

        except Exception as e:
            log.exception(e)
            log.info("%s:unexpected error: %s", self.prof_name, str(e))

        finally:
            on_stop_cb(self.prof_id, retcode)
            log.info("%s:return code %s", self.prof_name, retcode)

            self.stop()
            self.process = None


    def stop(self):
        if self.is_active():
            self.process.terminate()
            # Send the signal to all the process groups
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)

    def is_active(self):
        return self.process is not None

    def get_env(self, environ_options):
        env = os.environ.copy()

        for opt in environ_options:
            eq_sign = opt.find("=")
            if eq_sign > 0:
                key, val = opt[0:eq_sign], opt[eq_sign+1:]
                env[key] = val

        return env

