# -*- coding: utf-8 -*-
# vim: sw=4 ts=4 fenc=utf-8 et
# ==============================================================================
# Copyright © 2010 UfSoft.org - Pedro Algarvio <ufs@ufsoft.org>
#
# License: BSD - Please view the LICENSE file for additional information.
# ==============================================================================

from formless import annotate
from nevow import util
from twisted.python import reflect
from zope.interface import Attribute

class ConfigFileMixIn(Attribute):
    unicode = True
    convert_to = None
    convert_from = None

    def to_string(self):
        if not self.convert_to:
            raise NotImplementedError("Implement in %s" %
                                      util.qual(self.__class__))
        return self.convert_to()

    def from_string(self, string):
        if not self.convert_from:
            raise NotImplementedError("Implement in %s" %
                                      util.qual(self.__class__))
        self.value = self.convert_from(string)


class String(annotate.String, ConfigFileMixIn):

    def convert_to(self):
        if self.default:
            return self.default.encode('utf-8')
        return ''

    def convert_from(self, string):
        self.default = string.decode('utf-8')


class Text(String):
    pass


class Password(String):
    pass


class PasswordEntry(String):
    pass


class Integer(annotate.Integer, ConfigFileMixIn):

    def convert_to(self):
        return str(self.default)
    def convert_from(self, string):
        self.default = int(string)


class Real(annotate.Real, ConfigFileMixIn):
    def convert_to(self):
        return str(self.default)
    def convert_from(self, string):
        self.default = float(string)


class Boolean(annotate.Boolean, ConfigFileMixIn):
    def convert_to(self):
        return str(self.default)

    def convert_from(self, string):
        if string.lower() in ('true', '1'):
            self.default = True
        elif string.lower() in ('false', '0'):
            self.default = False
        else:
            raise annotate.InputError("'%s' is not a boolean" % string)


class Choice(annotate.Choice, ConfigFileMixIn):
    def convert_to(self):
        return self.default
    def convert_from(self, string):
        self.default = string

current_locals = locals().keys()
for klass_name in dir(annotate):
    if klass_name not in current_locals:
        klass = getattr(annotate, klass_name)
        try:
            if annotate.Typed in reflect.allYourBase(klass):
                locals()[klass_name] = klass
        except:
            pass
        del klass
del current_locals

if __name__ == '__main__':
#    print dir(annotate)
    print locals(), len(locals())

