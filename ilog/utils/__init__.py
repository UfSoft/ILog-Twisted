# -*- coding: utf-8 -*-
# vim: sw=4 ts=4 fenc=utf-8 et
# ==============================================================================
# Copyright © 2010 UfSoft.org - Pedro Algarvio <ufs@ufsoft.org>
#
# License: BSD - Please view the LICENSE file for additional information.
# ==============================================================================

from nevow import inevow, tags, entities
from os.path import dirname, join
from twisted.python import util
from ilog.ifaces import IFlashMessages

JS_DIR = join(util.sibpath(dirname(__file__), 'static'), 'js')
STYLE_DIR = join(util.sibpath(dirname(__file__), 'static'), 'style')
IMAGES_DIR = join(util.sibpath(dirname(__file__), 'static'), 'img')
TEMPLATES_DIR = util.sibpath(dirname(__file__), 'templates')
FAVICON_ICO = join(IMAGES_DIR, 'favicon.ico')

def get_template(template_name):
    return join(TEMPLATES_DIR, *(template_name.split('/')))

def flash(ctx, message_contents, message_type='info'):
    assert message_type in ('info', 'add', 'remove', 'error', 'ok', 'configure',
                            'warning')
    session = inevow.IRequest(ctx).session
    messages = IFlashMessages(session)
    if message_type == 'error':
        message_contents = tags.invisible[
            tags.b["Error:"], entities.nbsp, message_contents
        ]
    elif message_type == 'warning':
        message_contents = tags.invisible[
            tags.b["Warning:"], entities.nbsp, message_contents
        ]
    messages.append((message_type, message_contents))
