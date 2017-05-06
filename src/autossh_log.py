#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Created on 06.05.17 17:13

@author: pavel
"""
import sys
import logging
import collections

log = logging.getLogger() #root logger
#Have to set the root logger level, it defaults to logging.WARNING
log.setLevel(logging.NOTSET)


# Python logging split between stdout and stderr
# http://stackoverflow.com/questions/16061641/python-logging-split-between-stdout-and-stderr
class InfoFilter(logging.Filter):
    def filter(self, rec):
        return rec.levelno in (logging.DEBUG, logging.INFO)


stdout_hadler = logging.StreamHandler(sys.stdout)
stdout_hadler.setLevel(logging.DEBUG)
stdout_hadler.addFilter(InfoFilter())

stderr_handler = logging.StreamHandler()
stderr_handler.setLevel(logging.WARNING)

log.addHandler(stdout_hadler)
log.addHandler(stderr_handler)


#My logger
class LimLogHandler(logging.Handler):
    def __init__(self, buffer_size = 100):
        super(LimLogHandler, self).__init__()
        self.setFormatter(LogFormatter())
        self.circular_buffer = collections.deque(maxlen = buffer_size)
        self.observers = {}

        #set level
        self.setLevel(logging.INFO)
        #register itself as global handler
        log.addHandler(self)


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
            log.info(_("Observer %s unregistered"), obs_name)

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


