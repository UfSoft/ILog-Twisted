# -*- coding: utf-8 -*-
# vim: sw=4 ts=4 fenc=utf-8 et
# ==============================================================================
# Copyright © 2010 UfSoft.org - Pedro Algarvio <ufs@ufsoft.org>
#
# License: BSD - Please view the LICENSE file for additional information.
# ==============================================================================

import re
import unicodedata
from ilog.utils.translit_tab import LONG_TABLE, SHORT_TABLE, SINGLE_TABLE


_punctuation_re = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')
_string_inc_re = re.compile(r'(\d+)$')
_placeholder_re = re.compile(r'%(\w+)%')

def gen_slug(text, delim=u'-'):
    result = []
    for word in _punctuation_re.split(text.lower()):
        word = _punctuation_re.sub(u'', transliterate(word))
        if word:
            result.append(word)
    return unicode(delim.join(result))

def transliterate(string, table='long'):
    """Transliterate to 8 bit using one of the tables given.  The table
    must either be ``'long'``, ``'short'`` or ``'single'``.
    """
    table = {
        'long':     LONG_TABLE,
        'short':    SHORT_TABLE,
        'single':   SINGLE_TABLE
    }[table]
    return unicodedata.normalize('NFKC', unicode(string)).translate(table)
