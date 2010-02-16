# -*- coding: utf-8 -*-
# vim: sw=4 ts=4 fenc=utf-8 et
# ==============================================================================
# Copyright © 2010 UfSoft.org - Pedro Algarvio <ufs@ufsoft.org>
#
# License: BSD - Please view the LICENSE file for additional information.
# ==============================================================================

import logging
from nevow import inevow, guard
from zope.interface import Attribute, implements, Interface
from twisted.python.components import registerAdapter

from ilog.database import db

log = logging.getLogger(__name__)

__all__ = ["IFlashMessages", "IDBSession"]

class IFlashMessages(Interface):
    messages = Attribute("List of messages to flash")

    def __iter__():
        """Yield messages by pop'ing them, cleaning existing messages"""

    def append(message):
        """add message"""

class FlashMessages(object):
    implements(IFlashMessages)

    def __init__(self, guard_session, messages=[]):
        self.guard = guard_session
        self.messages = messages

    def __iter__(self):
        while self.messages:
            yield self.messages.pop(0)

    def append(self, message):
        self.messages.append(message)


registerAdapter(FlashMessages, guard.GuardSession, IFlashMessages)


class IDBSession(Interface):

    _session = Attribute("Sqlalchemy database session.")

    def session():
        """Instantiate and return an SQLAlchemy session"""

    def close_session():
        """Close the database session"""

class DBSession(object):
    implements(IDBSession)

    _session = None

    def __init__(self, request):
        self.request = request

    @property
    def session(self):
        if not self._session:
            self._session = db.session()
            log.debug("Opened database session. ID: %s",
                      self._session.hash_key)
            self.request.notifyFinish().addCallback(self.close_session)
        else:
            log.debug("Returning already opened database session ID: %s",
                      self._session.hash_key)
        return self._session

    def close_session(self, result):
        if result is not None:
            log.exception("\n\n\nException found on session ID: %s!!! %s\n\n\n",
                          self._session.hash_key, result)
            # Rollback session!?!?!?
        log.debug("Closing database session ID: %s",
                  self._session.hash_key)
        self._session.close()

registerAdapter(DBSession, inevow.IRequest, IDBSession)
#registerAdapter(DBSession, inevow.IGuardSession, IDBSession)
