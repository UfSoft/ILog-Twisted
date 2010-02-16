# -*- coding: utf-8 -*-
# vim: sw=4 ts=4 fenc=utf-8 et
# ==============================================================================
# Copyright © 2010 UfSoft.org - Pedro Algarvio <ufs@ufsoft.org>
#
# License: BSD - Please view the LICENSE file for additional information.
# ==============================================================================

from ConfigParser import SafeConfigParser
from os.path import abspath, basename, dirname, exists, expanduser, isdir, join
from ilog.utils.annotate import (Boolean, Integer, Password, Real, String, Text,
                                 Choice)

def get_engine_choices(ctx, data):
    return ['mysql', 'postgres', 'oracle', 'mssql', 'firebird']

DB_ENGINES = Choice(choices=get_engine_choices, default='postgres')


DEFAULT_CONFIG = {
    # Section
    'main': {
        'logging_config_file': String(label="Logging Config File:",
                                      default="%(here)s/logging.ini",
                                      description="The path to the logging "
                                                  "configuration file.")
    },
    'serve': {
        'port': Integer(label="Port:", default=8080,
                        description="Web service port"),
    },
    'web':{
        'cookie_name': String(label="Cookie Name:", default='ilog_cookie',
                              description="The name of the cookie that will "
                              "be sent to the user."),
    },
    'rpxnow': {
        'api_key': String(label="Api Key:", description="RPXNow.com API key"),
        'app_domain': String(label="Application Domain:",
                             description="RPXNow.com application domain"),
    },
    'database': {
        'engine': Choice(choices=get_engine_choices, default='postgres',
                         label="Engine:", required=True,
                         description="Database Engine"),
        'username': String(label="Username:",
                           description="Database engine username"),
        'password': String(label="Username:",
                           description="Database engine password"),
        'name': String(label="Name:", description="Database name"),
        'host': String(label="Host:", default='localhost',
                       description="Database host address"),
        'port': Integer(label="Port:", default=5432,
                        description="Database host port"),
        'debug_sql': Boolean(label="Debug SQL:", default=False,
                             descriprion="Turn on some very extremely verbose "
                                         "messages to the logs")
    }
}

class ConfigurationSection(object):
    def __init__(self, section, items):
        self.section = section
        self.values = {}
        for item_name, item in items.iteritems():
            self.values[item_name] = item

    @property
    def __dict__(self):
        return self.values.copy()

    def __getattr__(self, key):
        return self.values[key].default

    def set(self, key, value):
        if key in self.values:
            self.values[key].default = value

    def raw_dict(self):
        d = {}
        for name, item in self.values.iteritems():
            d[name] = item.to_string()
        return d

class Configuration(object):
    exists = True

    def __init__(self, filename):
        self.filename = filename
        self.sections = {}
        self.values = {}
        for section, items in DEFAULT_CONFIG.copy().iteritems():
            if section == 'main':
                for item_name, item in items.iteritems():
                    self.values[item_name] = item
                continue
            self.sections[section] = ConfigurationSection(section, items)
        self.parser = SafeConfigParser()
        if not exists(filename):
            self.exists = False
        if self.exists:
            # update values from configuration
            self.parser.read([filename])
            self.parser.set('DEFAULT', 'here', dirname(filename))
            for section in self.parser.sections():
                if section == 'DEFAULT':
                    continue
                for option in self.parser.options(section):
                    if option == 'here':
                        continue
                    if section == 'main':
                        target = self.values[option]
                    else:
                        target = self.sections[section].values[option]
                    target.from_string(self.parser.get(section, option))

    def __getattr__(self, key):
        if key in self.sections:
            return self.sections[key]
        elif key == '__dict__':
            d = self.values.copy()
            for section in self.sections:
                d[section] = self.sections[section].__dict__.copy()
            return d
        return self.values[key].default

    def pprint(self):
        import pprint
        pprint.pprint(self.raw_dict())

    def raw_dict(self):
        d = {}
        for name, item in self.values.iteritems():
            d[name] = item.to_string()
        for section in self.sections:
            d[section] = {}
            for name, item in self.sections[section].values.iteritems():
                d[section][name] = item.to_string()
        return d

    def set(self, key, value):
        if key in self.values:
            self.values[key].default = value

    def save(self, filename=None):
        if not self.parser.has_section('main'):
            self.parser.add_section('main')
        for key, item in self.values.iteritems():
            self.parser.set('main', key, item.to_string())
        for section, section_item in self.sections.iteritems():
            if not self.parser.has_section(section):
                self.parser.add_section(section)
            for key, item in section_item.values.iteritems():
                self.parser.set(section, key, item.to_string())

        self.parser.remove_option('DEFAULT', 'here')
        self.parser.remove_section('DEFAULT')
        self.parser.write(open(filename or self.filename, 'w'))


if __name__ == '__main__':
    config = Configuration('foo.txt')
    print config.cookie_name, type(config.cookie_name), repr(config.cookie_name)
#    config.set('cookie_name', 'cookie_foo')
    print config.cookie_name, type(config.cookie_name), repr(config.cookie_name)

    print config.serve.port
    config.serve.set('port', 9090)
    print config.serve.port
    config.save('foo.txt')
