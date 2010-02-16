#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: sw=4 ts=4 fenc=utf-8 et
# ==============================================================================
# Copyright © 2010 UfSoft.org - Pedro Algarvio <ufs@ufsoft.org>
#
# License: BSD - Please view the LICENSE file for additional information.
# ==============================================================================


import csv
import os
from distutils import cmd
from distutils.command.build import build as _build
from distutils.command.clean import clean
from distutils.command.install import install as _install
from setuptools import setup
from setuptools.command.develop import develop as _develop
import ilog

class build_translit(cmd.Command):
    description = "Build the unicode translation tables"

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def read_table(self, path):
        long, short, single = {}, {}, {}

        t = open(path)
        for line in t.readlines():
            if not line.startswith('<'):
                continue
            from_spec, raw_to = line.strip().split(' ', 1)
            from_ord = int(from_spec[2:-1], 16)

            raw = csv.reader([raw_to], 'transtab').next()
            long_char = self._unpack_uchrs(raw[0])
            if len(raw) < 2:
                short_char = long_char
            else:
                short_char = self._unpack_uchrs(raw[1])

            long[from_ord] = long_char
            short[from_ord] = short_char
            if len(short_char) == 1:
                single[from_ord] = short_char
        return long, short, single


    def _unpack_uchrs(self, packed):
        chunks = packed.replace('<U', ' ').strip().split()
        return ''.join(unichr(int(spec[:-1], 16)) for spec in chunks)

    def update_mapping(self, long, short, single, path):
        src = open(path)
        try:
            data = src.read()
            pos = 0
            for x in xrange(2):
                pos = data.find('"""', pos) + 1
            preamble = data[:pos + 3]
        finally:
            src.close()

        rewrite = open(path, 'wb')
        try:
            rewrite.writelines(preamble)
            self._dump_dict(rewrite, 'LONG_TABLE', long)
            self._dump_dict(rewrite, 'SHORT_TABLE', short)
            self._dump_dict(rewrite, 'SINGLE_TABLE', single)
        finally:
            rewrite.close()

    def _dump_dict(self, fh, name, data):
        fh.write('\n%s = {\n' % name)
        for pair in sorted(data.items()):
            fh.write('    %r: %r,\n' % pair)
        fh.write('}\n')

    def run(self):
        csv.register_dialect('transtab', delimiter=';')
        translitcodec_transtab_dir = os.path.join(os.path.dirname(__file__),
                                                  'extra', 'translitcodec',
                                                  'transtab')
        if os.path.isdir(translitcodec_transtab_dir):
            mapping_file = os.path.join(os.path.dirname(ilog.__file__),
                                        'utils', 'translit_tab.py')
            table = self.read_table(os.path.join(translitcodec_transtab_dir,
                                                 'transtab'))
            self.update_mapping(path=mapping_file, *table)
            print 'All done.'

class develop(_develop):
    def run(self):
        self.run_command('build_translit')
        _develop.run(self)

class build(_build):
    sub_commands = [('build_translit', None)] + _build.sub_commands

class install(_install):
    def run(self):
        for cmd_name in self.get_sub_commands():
            self.run_command(cmd_name)
        _install.run(self)
        if not self.root:
            self.do_egg_install()

cmdclass = {
    'build': build,
    'build_translit': build_translit,
    'develop': develop,
    'clean': clean,
    'install': install
}

setup(name=ilog.__package__,
      version=ilog.__version__,
      author=ilog.__author__,
      author_email=ilog.__email__,
      url=ilog.__url__,
      download_url='http://python.org/pypi/%s' % ilog.__package__,
      description=ilog.__summary__,
      long_description=ilog.__description__,
      license=ilog.__license__,
      platforms="OS Independent - Anywhere Twisted and PIL is known to run.",
      keywords = "Twisted PIL Web Picpost",
      cmdclass = cmdclass,
      packages=['ilog'],
      entry_points = """
      [console_scripts]
      irc-logger = ilog.bootstrap:daemon

      """,
      classifiers=[
          'Development Status :: 5 - Alpha',
          'Environment :: Web Environment',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: BSD License',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Utilities',
          'Topic :: Internet :: WWW/HTTP',
          'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
      ]
)
