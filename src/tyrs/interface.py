# -*- coding: utf-8 -*-
# Copyright © 2011 Nicolas Paris <nicolas.caen@gmail.com>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
import os
import tyrs
import urwid
import curses
import logging
from user import User
from keys import Keys
from help import help_bar, Help
from utils import get_urls
from constant import palette
from editor import TweetEditor
from update import UpdateThread
from widget import HeaderWidget
from completion import Completion
import urwid.html_fragment

class Interface(object):

    def __init__(self):
        self.api        = tyrs.container['api']
        self.conf       = tyrs.container['conf']
        self.timelines  = tyrs.container['timelines']
        self.buffers    = tyrs.container['buffers']
        self.completion = tyrs.container['completion']
        self.help = False
        tyrs.container.add('interface', self)
        self.update_last_read_home()
        self.api.set_interface()
        self.regex_retweet     = re.compile('^RT @\w+:')
        self.stoped = False
        self.buffer           = 'home'
        self.first_update()
        self.main_loop()

    def main_loop (self):

        self.header = HeaderWidget()
        foot = help_bar()
        self.listbox = self.select_current_timeline().timeline
        self.main_frame = urwid.Frame(urwid.AttrWrap(self.listbox, 'body'), header=self.header, footer=foot)
        key_handle = Keys()
        urwid.connect_signal(key_handle, 'help_done', self.help_done)
        self.loop = urwid.MainLoop(self.main_frame, palette, unhandled_input=key_handle.keystroke)
        update = UpdateThread()
        update.start()
        self.loop.run()
        update._Thread__stop()
        update.stop()

    def reply(self):
        self.status = self.current_status()
        if hasattr(self.status, 'user'):
            nick = self.status.user.screen_name
        #FIXME: 
        #else:
            #self.direct_message()
        data = '@' + nick
        self.edit_status('reply', data, 'Tweet ')

    def edit_status(self, action, content='', prompt=''):
        self.foot = TweetEditor(content, prompt)
        self.main_frame.set_footer(self.foot)
        self.main_frame.set_focus('footer')
        if action == 'tweet':
            urwid.connect_signal(self.foot, 'done', self.api.tweet_done)
        elif action == 'reply':
            urwid.connect_signal(self.foot, 'done', self.api.reply_done)
        elif action == 'follow':
            urwid.connect_signal(self.foot, 'done', self.api.follow_done)
        elif action == 'unfollow':
            urwid.connect_signal(self.foot, 'done', self.api.unfollow_done)
        elif action == 'search':
            urwid.connect_signal(self.foot, 'done', self.api.search_done)
        elif action == 'public':
            urwid.connect_signal(self.foot, 'done', self.api.public_done)
        elif action == 'list':
            urwid.connect_signal(self.foot, 'done', self.api.list_done)

    def first_update(self):
        updates = ['user_retweet', 'favorite']
        for buff in updates:
            self.api.update_timeline(buff)
            self.timelines[buff].reset()
            self.timelines[buff].all_read()

    def display_timeline (self):
        if not self.help:
            timeline = self.select_current_timeline()
            self.listbox = timeline.timeline
            self.main_frame.set_body(urwid.AttrWrap(self.listbox, 'body'))
            if self.buffer == 'home':
                self.conf.save_last_read(timeline.last_read)
            self.display_flash_message()

    def lazzy_load(self):
        timeline = self.select_current_timeline()
        focus = timeline.timeline.get_focus()[1]
        if timeline.cleared != False:
            return
        if focus is len(timeline.walker)-1:
            timeline.page += 1
            statuses = self.api.retreive_statuses(self.buffer, timeline.page)
            timeline.append_old_statuses(statuses)
            self.display_timeline()

    def redraw_screen (self):
        self.loop.draw_screen()

    def display_flash_message(self):
        if hasattr(self, 'main_frame'):
            header = HeaderWidget()
            self.main_frame.set_header(header)
            self.redraw_screen()
            self.api.flash_message.reset()

    def erase_flash_message(self):
        self.api.flash_message.reset()
        self.display_flash_message()

    def change_buffer(self, buffer):
        self.buffer = buffer
        self.timelines[buffer].reset()

    def navigate_buffer(self, nav):
        '''Navigate with the arrow, mean nav should be -1 or +1'''
        index = self.buffers.index(self.buffer)
        new_index = index + nav
        if new_index >= 0 and new_index < len(self.buffers):
            self.change_buffer(self.buffers[new_index])

    def check_for_last_read(self, id):
        if self.last_read_home == str(id):
            return True
        return False

    def select_current_timeline(self):
        return self.timelines[self.buffer]

    def clear_statuses(self):
        timeline = self.select_current_timeline()
        timeline.count_statuses()
        timeline.reset()
        timeline.clear()

    def current_status(self):
        focus = self.listbox.get_focus()[0]
        return focus.status

    def display_help(self):
        self.help = True
        h = Help()
        self.main_frame.set_body(h)

    def help_done(self):
        self.help = False
        self.display_timeline()

    def back_on_bottom(self):
        timeline = self.select_current_timeline()
        self.listbox.set_focus(timeline.status_count())

    def back_on_top(self):
        self.listbox.set_focus(0)

    def openurl(self):
        urls = get_urls(self.current_status().text)
        for url in urls:
            try:
                os.system(self.conf.params['openurl_command'] % url + '> /dev/null 2>&1')
            except:
                logging.error('openurl error')

    def update_last_read_home(self):
        self.last_read_home = self.conf.load_last_read()

    def current_user_info(self):
        User(self.current_status().user)

    def go_up(self):
        timeline = self.select_current_timeline()
        timeline.go_up()

    def go_down(self):
        timeline = self.select_current_timeline()
        timeline.go_down()

    def beep(self):
        return curses.beep()
