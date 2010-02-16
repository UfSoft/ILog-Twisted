# -*- coding: utf-8 -*-
# vim: sw=4 ts=4 fenc=utf-8 et
# ==============================================================================
# Copyright © 2010 UfSoft.org - Pedro Algarvio <ufs@ufsoft.org>
#
# License: BSD - Please view the LICENSE file for additional information.
# ==============================================================================

import sys
import logging
import threading

from time import time, strftime
from sqlalchemy.interfaces import ConnectionProxy
from nevow import inevow, loaders, livepage, tags as T, util
from nevow.livepage import set, assign, append, js, document, eol
from twisted.internet import task, defer, threads
from twisted.python import failure
from ilog import utils

log = logging.getLogger(__name__)

def find_calling_context(skip=3):
    """Finds the calling context."""
    frame = sys._getframe(skip)
    while frame.f_back is not None:
        name = frame.f_globals.get('__name__')
        if name and name.startswith('ilog.'):
            funcname = frame.f_code.co_name
            if 'self' in frame.f_locals:
                funcname = '%s.%s of %s' % (
                    frame.f_locals['self'].__class__.__name__,
                    funcname,
                    hex(id(frame.f_locals['self']))
                )
            return '%s:%s (%s)' % (
                frame.f_code.co_filename,
                frame.f_lineno,
                funcname
            )
        frame = frame.f_back

#    def print_frame_info(frame):
#        return 123456, frame.f_globals.get('__name__'), frame.f_code.co_name
#    try:
#        for n in range(100):
#            print n, print_frame_info(sys._getframe(n))
#    except ValueError:
#        print
    return '<unknown>'

def get_pretty_time(start, end=time()):
    d = end - start
    if d >= 1.0:
        return "took %.2f s" % d
    return "took %.3f ms" % (d*1000)

class DatabaseConnectionDebugProxy(threading.Thread, livepage.LivePage, ConnectionProxy):
    addSlash = True
    docFactory = loaders.xmlfile(utils.get_template('sql_debug.html'))
    messagePattern = inevow.IQ(docFactory).patternGenerator('message')

    def __init__(self, group=None, target=None, name=None, *args, **kwargs):
        threading.Thread.__init__(self, group, target, name, args, kwargs)
        self.start()
        livepage.LivePage.__init__(self)
        ConnectionProxy.__init__(self)
        self.queries = []
        self.clients = []

    def cursor_execute(self, execute, cursor, statement, parameters,
                       context, executemany):
        start = time()
#        defer.setDebugging(True)
        try:
            return execute(cursor, statement, parameters, context)
        finally:
            self.build_event(statement, context, start, time())
#            defer.setDebugging(False)

    def build_event(self, statement, context, start, end=time()):
        event = append(
            'entries',
            self.messagePattern.fillSlots(
                'statement', T.invisible[
                    [[util.escapeToXML(t), T.br]
                     for t in statement.splitlines()]
                ]
            ).fillSlots(
                'calling-context', find_calling_context()
            ).fillSlots(
                'time', get_pretty_time(start, end)
            )
        )
        self.sendEvent(event)

    def goingLive(self, ctx, client):
        client.notifyOnClose().addBoth(self.userLeft, client)

        ## Catch the user up with the previous events
        for event in self.queries:
            client.send(event, eol)
        client.send(js.scrollDown())
        self.clients.append(client)

    def userLeft(self, _, client):
        self.clients.remove(client)

    def sendEvent(self, event):
        self.queries.append(event)
        for target in self.clients:
            target.send(event, eol, js.scrollDown())
        return event
