# -*- coding: utf-8 -*-
"""
    ilog.database
    ~~~~~~~~~~~~~
    This module is a layer on top of SQLAlchemy to provide asynchronous
    access to the database and has the used tables/models used in ILog.

    :copyright: © 2010 UfSoft.org - Pedro Algarvio <ufs@ufsoft.org>
    :license: BSD, see LICENSE for more details.
"""

import os
import sys
import logging
import functools
from os import remove, removedirs
from os.path import basename, dirname, join, splitext
from hashlib import md5, sha1
from random import choice
from time import time
from types import ModuleType
from datetime import datetime

import sqlalchemy
from sqlalchemy import and_, or_
from sqlalchemy import orm
from sqlalchemy.exceptions import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (EXT_CONTINUE, MapperExtension, dynamic_loader,
                            deferred)

from nevow import inevow, context, rend
from twisted.internet import defer, threads

from ilog import application as app
from ilog.utils.crypto import gen_pwhash, check_pwhash
from ilog.utils.text import gen_slug

log = logging.getLogger(__name__)

def sqla_session(f):
    @functools.wraps(f)
    @defer.inlineCallbacks
    def deferred_processing(klass, *args, **kwargs):
        session = yield db.session()
        yield log.debug("Opening database session: %s", session.hash_key)

        try:
            try:
                result = yield defer.maybeDeferred(f, klass, sa_session=session,
                                                   *args, **kwargs)
            except TypeError, error:
                log.debug("%s:%s() does not accept sa_session as a kwarg",
                          klass.__class__.__name__, f.__name__)
#                yield log.exception(error)
                klass.sa_session = yield session
                log.debug("%s.sa_session attribute set to %s",
                          klass.__class__.__name__, klass.sa_session)
                result = yield defer.maybeDeferred(f, klass, *args, **kwargs)
            except Exception, error:
                log.debug("Something's else went wrong: %s", error)
                defer.returnValue(defer.fail(error))
            defer.returnValue(result)
        except SQLAlchemyError, error:
            yield log.debug("EXCEPTION CATCHED: Rolling back session: %s",
                            session.hash_key)
            yield log.exception(error)
            yield threads.deferToThread(session.rollback)
            defer.returnValue(error)
        except Exception, error:
            yield log.exception(error)
            defer.returnValue(defer.fail(error))
#            defer.returnValue(error)
        finally:
            if session.dirty:
                # Forgot to commit!!?!?!??
                yield log.warning("Forgot to commit session on %s.%s()???."
                                  " commit()",
                                  klass.__class__.__name__, f.__name__)
                yield threads.deferToThread(session.commit)
            yield log.debug("Closing database session: %s", session.hash_key)
            yield threads.deferToThread(session.close)
            if hasattr(klass, 'sa_session'):
                del klass.sa_session
    return deferred_processing

def sqla_session_inline_callbacks(f):
    return sqla_session(defer.inlineCallbacks(f))

def get_engine():
    """Return the active database engine (the database engine of the active
    application).  If no application is enabled this has an undefined behavior.
    If you are not sure if the application is bound to the active thread, use
    :func:`~zine.application.get_application` and check it for `None`.
    The database engine is stored on the application object as `database_engine`.
    """
    from ilog import application
    return application.database_engine


#: create a new module for all the database related functions and objects
sys.modules['ilog.database.db'] = db = ModuleType('db')
key = value = mod = None
for mod in sqlalchemy, orm:
    for key, value in mod.__dict__.iteritems():
        if key == 'create_engine':
            continue
        if key in mod.__all__:
            setattr(db, key, value)
del key, mod, value
db.and_ = and_
db.or_ = or_
#del and_, or_


db.session = None   # This is set upon application startup
db.DeclarativeBase = DeclarativeBase = declarative_base()
db.metadata = metadata = DeclarativeBase.metadata
db.sqla_session = sqla_session
db.sqla_session_inline_callbacks = sqla_session_inline_callbacks

log = logging.getLogger(__name__)

class User(DeclarativeBase):
    __tablename__ = 'users'

    username            = db.Column(db.String(20), primary_key=True)
    identifier          = db.Column(db.String)
    display_name        = db.Column(db.String(30), default="Anonymous")
    #session_id          = db.Column(db.ForeignKey('sessions.id'), default=None)
    email               = db.Column(db.String)
    active              = db.Column(db.Boolean, default=False)
    confirmed           = db.Column(db.Boolean, default=False)
    passwd_hash         = db.Column(db.String)
    last_used           = db.Column(db.DateTime, default=datetime.utcnow())
    last_login          = db.Column(db.DateTime, default=datetime.utcnow())
    agreed_to_tos       = db.Column(db.Boolean, default=False)
    is_admin            = db.Column(db.Boolean, default=False)
    items_per_page      = db.Column(db.Integer, default=15)
    tzinfo              = db.Column(db.String(25), default="UTC")

    def __init__(self, username=None, identifier=None, display_name=None,
                 email=None, active=False, confirmed=False, passwd=None,
                 agreed_to_tos=False, is_admin=False):
        self.username = username
        self.identifier = identifier
        if display_name:
            self.display_name = display_name
        else:
            self.display_name = username and username or identifier
        if email:
            self.email = email
        self.active = active
        self.confirmed = confirmed
        if passwd:
            self.set_password(passwd)
        self.agreed_to_tos = agreed_to_tos
        self.is_admin = is_admin

    def __repr__(self):
        return "<User %s>" % (self.username or 'annonymous')

    def to_dict(self):
        return {
            'email': self.email,
            'username': self.username,
            'is_admin': self.is_admin,
            'confirmed': self.confirmed,
            'identifier': self.identifier,
            'display_name': self.display_name,
            'agreed_to_tos': self.agreed_to_tos
        }

    @property
    def public_username(self):
        return self.username.split('@')[0]

    def set_password(self, password):
        self.passwd_hash = gen_pwhash(password)

    def authenticate(self, password):
        if self.confirmed and check_pwhash(self.passwd_hash, password):
#            session = db.session()
            self.touch()
            self.last_login = datetime.utcnow()
#            session.commit()
#            session.close()
            return True
        return False

    def pre_authenticate(self, password=None):
        return True

    def touch(self):
        self.last_used = datetime.utcnow()

class Bot(DeclarativeBase):
    __tablename__ = 'bots'

    name    = db.Column(db.String, primary_key=True)
    user_id = db.Column(db.ForeignKey('users.username'))


class Network(DeclarativeBase):
    __tablename__ = 'networks'

    name    = db.Column(db.String, primary_key=True)
    address = db.Column(db.String, nullable=False)
    port    = db.Column(db.Integer, nullable=False)


class NetworkParticipation(DeclarativeBase):
    __tablename__ = 'network_participations'

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    bot_id        = db.Column(db.ForeignKey('bots.name'))
    network_name  = db.Column(db.ForeignKey('networks.name'))
    nick          = db.Column(db.String, nullable=False)
    password      = db.Column(db.String)


class Identity(DeclarativeBase):
    __tablename__  = 'identities'
    __table_args__ = (db.UniqueConstraint('network_name', 'nick'), {})

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    network_name   = db.Column(db.ForeignKey('networks.name'))
    nick           = db.Column(db.String(64))
    realname       = db.Column(db.String(128))
    ident          = db.Column(db.String(64))
    user_id        = db.Column(db.ForeignKey('users.username'), default=None)


class Channel(DeclarativeBase):
    __tablename__  = 'channels'
    __table_args__ = (db.UniqueConstraint('network_name', 'name', 'prefix'), {})

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name           = db.Column(db.String, index=True)
    network_name   = db.Column(db.ForeignKey('networks.name'), index=True)
    prefix         = db.Column(db.String(3))
    key            = db.Column(db.String, nullable=True)

    # Topic Related
    topic         = db.Column(db.String)
    changed_on    = db.Column('topic_changed_on', db.DateTime(timezone=True))
    changed_by_id = db.Column('topic_changed_by_identity_id',
                              db.ForeignKey('identities.id'))


class Event(DeclarativeBase):
    __tablename__  = 'events'
    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    channel_id     = db.Column(db.ForeignKey('channels.id'), index=True)
    stamp          = db.Column(db.DateTime(timezone=True))
    type           = db.Column(db.String(10))
    identity_id    = db.Column(db.ForeignKey('identities.id'), index=True)
    message        = db.Column(db.String)



class Session(DeclarativeBase):
    __tablename__ = 'sessions'

    id          = db.Column(db.String(32), primary_key=True)
    last_used   = db.Column(db.Float, default=time())
    user_id     = db.Column(db.ForeignKey('users.username'), default=None)

    # Relations
    authenticated_as = db.relation(User, backref='session', uselist=False)

    def __init__(self, id):
        self.id = id
        self.touch()

    def touch(self):
        self.last_used = time()

    def renew(self):
        self.last_used = time()

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self.id)


