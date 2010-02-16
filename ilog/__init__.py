# -*- coding: utf-8 -*-
# vim: sw=4 ts=4 fenc=utf-8 et
# ==============================================================================
# Copyright © 2010 UfSoft.org - Pedro Algarvio <ufs@ufsoft.org>
#
# License: BSD - Please view the LICENSE file for additional information.
# ==============================================================================

"""
IRC Logging
===========

"""

__version__     = '0.1'
__package__     = 'ILog'
__summary__     = "IRC Logging"
__author__      = 'Pedro Algarvio'
__email__       = 'ufs@ufsoft.org'
__license__     = 'BSD'
__url__         = 'https://hg.ufsoft.org/ILog'
__description__ = __doc__

import sys
from types import ModuleType

sys.modules['ilog.application'] = application = ModuleType( 'application' )
sys.modules['ilog.notification'] = notification = ModuleType( 'notification' )
