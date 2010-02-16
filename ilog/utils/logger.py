# -*- coding: utf-8 -*-
"""
    ilog.utils.logger
    ~~~~~~~~~~~~~~~~~

    This module defines a custom logging class which allows python's logging
    to be used asynchronously with twisted.

    :copyright: © 2010 UfSoft.org - Pedro Algarvio <ufs@ufsoft.org>
    :license: BSD, see LICENSE for more details.
"""

import logging
from twisted.internet import defer

LoggingLoggerClass = logging.getLoggerClass()

class Logging(LoggingLoggerClass):
    def __init__(self, logger_name='ilog', level=logging.DEBUG):
        LoggingLoggerClass.__init__(self, logger_name, level)

    @defer.inlineCallbacks
    def debug(self, msg, *args, **kwargs):
        yield LoggingLoggerClass.debug(self, msg, *args, **kwargs)

    @defer.inlineCallbacks
    def info(self, msg, *args, **kwargs):
        yield LoggingLoggerClass.info(self, msg, *args, **kwargs)

    @defer.inlineCallbacks
    def warning(self, msg, *args, **kwargs):
        yield LoggingLoggerClass.warning(self, msg, *args, **kwargs)

    warn = warning

    @defer.inlineCallbacks
    def error(self, msg, *args, **kwargs):
        yield LoggingLoggerClass.error(self, msg, *args, **kwargs)

    @defer.inlineCallbacks
    def critical(self, msg, *args, **kwargs):
        yield LoggingLoggerClass.critical(self, msg, *args, **kwargs)

    @defer.inlineCallbacks
    def exception(self, msg, *args, **kwargs):
        yield LoggingLoggerClass.exception(self, msg, *args, **kwargs)

