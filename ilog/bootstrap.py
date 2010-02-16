# -*- coding: utf-8 -*-
# vim: sw=4 ts=4 fenc=utf-8 et
"""
    ilog.bootstrap
    ~~~~~~~~~~~~~~

    This module is responsible for console usage options.

    :copyright: © 2010 UfSoft.org - Pedro Algarvio <ufs@ufsoft.org>
    :license: BSD, see LICENSE for more details.
"""

import logging
import logging.config
import getpass
from os import makedirs, environ
from os.path import abspath, basename, expanduser, isdir, join
from twisted.internet import reactor
from twisted.python import usage
from twisted.python.log import PythonLoggingObserver

from ilog import __version__, application as app, config

usefull_path = lambda path: abspath(expanduser(path))

class NoAdminException(Exception):
    """Exception raised where there's still no admin user"""

class SysExit(BaseException):
    def __init__(self, msg, *args, **kwargs):
        BaseException.__init__(self, msg % args % kwargs)
        print msg % args % kwargs
        exit(kwargs.pop('code', 1))

class BaseUsageOptions(usage.Options):
    parser = None
    # Hack Start
    def loadConfigFileOptions(self, subCommand):
        dont_dispatch = ['help', 'version']
        if self.parser:
            for key in self.defaults.iterkeys():
                if self.parser.has_section(subCommand) and \
                                    self.parser.has_option(subCommand, key):
                    config_value = self.parser.get(subCommand, key)
                    self.defaults[key] = config_value

                    if key not in dont_dispatch:
                        try:
                            if callable(self._dispatch[key]):
                                self._dispatch[key](key, config_value)
                            else:
                                self._dispatch[key].dispatch(key, config_value)
                        except SysExit:
                            print "Option error in configuration file under",
                            print "the section %s variable %s" % (subCommand,
                                                                  key)
                            raise
#                        if key not in self.opts:
#                            self.opts[key] = self.opts[key] = config_value
#                    else:
#                        self.defaults[key] = config_value
    # Hack End

    def parseOptions(self, options=None):
        """
        The guts of the command-line parser.
        """
        if options is None:
            options = usage.sys.argv[1:]
        try:
            opts, args = usage.getopt.getopt(options,
                                             self.shortOpt, self.longOpt)
        except usage.getopt.error, e:
            raise usage.UsageError(str(e))

        for opt, arg in opts:
            if opt[1] == '-':
                opt = opt[2:]
            else:
                opt = opt[1:]

            optMangled = opt
            if optMangled not in self.synonyms:
                optMangled = opt.replace("-", "_")
                if optMangled not in self.synonyms:
                    raise usage.UsageError("No such option '%s'" % (opt,))

            optMangled = self.synonyms[optMangled]

            if isinstance(self._dispatch[optMangled], usage.CoerceParameter):
                self._dispatch[optMangled].dispatch(optMangled, arg)
            else:
                self._dispatch[optMangled](optMangled, arg)

        if (getattr(self, 'subCommands', None)
            and (args or self.defaultSubCommand is not None)):
            if not args:
                args = [self.defaultSubCommand]
            sub, rest = args[0], args[1:]
            for (cmd, short, parser, doc) in self.subCommands:
                if sub == cmd or sub == short:
                    self.subCommand = cmd
                    self.subOptions = parser()
                    self.subOptions.parent = self
                    # Hack Start
                    if hasattr(self, 'parser'):
                        self.subOptions.parser = self.parser
                    self.subOptions.loadConfigFileOptions(cmd)
                    # Hack End
                    self.subOptions.parseOptions(rest)
                    break
            else:
                raise usage.UsageError("Unknown command: %s" % sub)
        else:
            try:
                self.parseArgs(*args)
            except TypeError:
                raise usage.UsageError("Wrong number of arguments.")

        self.postOptions()

    def opt_version(self):
        """Show version"""
        print basename(usage.sys.argv[0]), '- %s' % __version__
    opt_v = opt_version

    def opt_help(self):
        """Show this help message"""
        usage.Options.opt_help(self)
    opt_h = opt_help

    def postOptions(self):
        self.parent.postOptions()
        self.executeCommand()

class RunServerOptions(BaseUsageOptions):
    "Run Server"
    longdesc = __doc__

    optParameters = [
        ["port", "p", 58846, "Port to bind to", int],
    ]

    def opt_port(self, port):
        self.opts['port'] = int(port)

    def executeCommand(self):
        import warnings
        # Shut up "twisted.web.error.NoResource is deprecated since Twisted 9.0.
        warnings.filterwarnings('ignore', category=DeprecationWarning,
                                module=r'nevow\.static')
#        from screener.views.main import build_site
#        site = build_site()
        # Warnings can now be reset
        warnings.resetwarnings()
        reactor.listenTCP(self.opts['port'], site)
        reactor.run()

class ServiceOptions(BaseUsageOptions):
    optParameters = [
        ("config", "c", "~/.ilog", "Configuration directory"),
    ]

    subCommands = [
        ["serve", None, RunServerOptions, RunServerOptions.__doc__]
    ]

    defaultSubCommand = "serve"

    def opt_config(self, config_dir):
        self.opts['config'] = usefull_path(config_dir)
        if not isdir(self.opts['config']):
            makedirs(self.opts['config'])

        config_dir = self.opts['config']
        config_file = usefull_path(join(self.opts['config'], 'ilog.ini'))
        app.config = config.Configuration(config_file)
        if not app.config.exists:
            app.config.save()
            raise SysExit("Initial configuration has been written to %s.\n"
                      "Please check it before running again.", config_file,
                      code=0)
        self.parser = app.config.parser

    def _setup_database(self):

        from ilog.database import db, DeclarativeBase, User, orm
        from sqlalchemy.exceptions import OperationalError, ProgrammingError

        def create_database_engine():
            from sqlalchemy import create_engine
            from sqlalchemy.engine.url import make_url

            if app.config.database.username and app.config.database.password:
                uri = '%(engine)s://%(username)s:%(password)s@%(host)s/%(name)s'
            if app.config.database.username and not app.config.database.password:
                uri = '%(engine)s://%(username)s@%(host)s/%(name)s'
            else:
                uri = '%(engine)s://%(host)s/%(name)s'
            info = make_url(uri % app.config.database.raw_dict())
            if info.drivername == 'mysql':
                info.query.setdefault('charset', 'utf8')
            options = {'convert_unicode': True,
                       'echo': False, 'echo_pool': False, 'echo_uow': False}
            if app.config.database.debug_sql:
                from ilog.utils.sql_debug import DatabaseConnectionDebugProxy
                app.config.database.debug_proxy = DatabaseConnectionDebugProxy()
                print 'Connection proxy'
                options['proxy'] = app.config.database.debug_proxy
            # alternative pool sizes / recycle settings and more.  These are
            # interpreter wide and not from the config for the following reasons:
            #
            # - system administrators can set it independently from the webserver
            #   configuration via SetEnv and friends.
            # - this setting is deployment dependent should not affect a development
            #   server for the same instance or a development shell
            for key in 'pool_size', 'pool_recycle', 'pool_timeout':
                value = environ.get('ILOG_DATABASE_' + key.upper())
                if value is not None:
                    options[key] = int(value)
            try:
                engine =  create_engine(info, **options)
            except TypeError:
                options.pop('echo_uow')
                engine = create_engine(info, **options)
            return engine


        def create_admin_user():
            def ask_detail(question):
                detail = raw_input(question)
                if not detail:
                    ask_detail(question)
                return detail

            def ask_password():
                try:
                    # It's not a password being requested, it's a password to define
                    passwd = getpass.getpass("Define a password for the new user:")
                    if not passwd:
                        return ask_password()
                    verify_password = getpass.getpass("Verify Password:")
                    if passwd != verify_password:
                        print "Passwords do not match."
                        return ask_password()
                    return passwd
                except KeyboardInterrupt:
                    exit(1)

            print "Creating initial administrator user"
            username = ask_detail("Initial Admin Username:")
            if '@' not in username:
                print "The username will be %s" % username,
                print "however this user will only be able to login to",
                print "an installation served from localhost like a local",
                print "testing machine."
                print "If this is a web server installation please provide:"
                print "  %s@domain.tld" % username
                username += "@localhost"
            else:
                uname, hname = username.split('@')
                print "Your username %s will only be able to" % uname,
                print "login to an installation served from %s" % hname
            email = ask_detail("Email Address:")
            password = ask_password()

            session = db.session()
            user = User(username=username, email=email, confirmed=True,
                        passwd=password, is_admin=True, agreed_to_tos=True)
            session.add(user)
            session.commit()

        app.database_engine = create_database_engine()
        try:
            app.database_engine.connect()
        except OperationalError, error:
            SysExit("Something wen't wrong connecting to the database: %s",
                    error.message)
        app.config.database.session = db.session = orm.sessionmaker(
            app.database_engine
        )
        DeclarativeBase.metadata.bind = app.database_engine

        if 'RESET_ILOG_DATABASE' in environ:
            if app.database_engine.has_table(User.__tablename__):
                print 'Dropping current database'
                db.metadata.drop_all(app.database_engine)
                SysExit("Current database dropped", code=0)
            SysExit("Database does not yet exist. Can't drop it!")

        if not app.database_engine.has_table(User.__tablename__):
            # Database was not created yet
            print "Creating database"
            db.metadata.create_all(app.database_engine)

        try:
            session = db.session()
            initial_user = session.query(User).first()
            if not initial_user:
                try:
                    create_admin_user()
                except KeyboardInterrupt:
                    raise SysExit("\nInterrupted by user")
        except ProgrammingError, error:
            raise SysExit(error.message)
        finally:
            session.close()

    def postOptions(self):
        if self.opts['config'] == "~/.ilog":
            self.opt_config(self.opts['config'])

        # Setup logging
        from ilog.utils.logger import Logging
        if logging.getLoggerClass() is not Logging:
            logging.config.fileConfig(
                usefull_path(str(app.config.logging_config_file))
            )
            logging.setLoggerClass(Logging)

            twisted_logging = PythonLoggingObserver('twisted')
            twisted_logging.start()

        self._setup_database()

        if not self.subCommand:
            self.opt_help()


def daemon():
    runner = ServiceOptions()
    try:
        runner.parseOptions() # When given no argument, parses sys.argv[1:]
    except usage.UsageError, errortext:
        raise SysExit('%s: %s\n%s: Try --help for usage details.',
                      usage.sys.argv[0], errortext, usage.sys.argv[0])

if __name__ == '__main__':
    daemon()
