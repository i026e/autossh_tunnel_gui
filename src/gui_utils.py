#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Created on 05.05.17 16:11

@author: pavel
"""
import os

from gi.repository import GObject
from gi.repository import Gtk

# decorator for safely update Gtk
def idle_add_decorator(func):
    def callback(*args):
        GObject.idle_add(func, *args)
    return callback

def read_iterable(iterable):
    model = iterable.get_model()
    iter_ = iterable.get_active_iter()

    return model.get_value(iter_, 0)

def write_iterable(iterable, value):
    model = iterable.get_model()
    iter_ = model.get_iter_first()
    while iter_ is not None:
        if model.get_value(iter_, 0) == value:
            iterable.set_active_iter(iter_)
            break
        iter_ = model.iter_next(iter_)

def read_textview(text_view):
    buffer = text_view.get_buffer()
    start_iter = buffer.get_start_iter()
    end_iter = buffer.get_end_iter()
    return buffer.get_text(start_iter, end_iter, True).split(os.linesep)

def write_textview(text_view, text_list):
    text = os.linesep.join(text_list)
    buffer = text_view.get_buffer()
    buffer.set_text(text)

def get_confirmation(parent_widget, message):
    dialog = Gtk.MessageDialog(parent = parent_widget,
                            flags=0,
                            type=Gtk.MessageType.QUESTION,
                            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                    Gtk.STOCK_OK, Gtk.ResponseType.OK),
                            message_format=message)
    response = dialog.run()
    confirm = response == Gtk.ResponseType.OK
    dialog.destroy()
    return confirm