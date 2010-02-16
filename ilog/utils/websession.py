# Copyright 2005 Divmod, Inc.  See LICENSE file for details

# Adaptation to ILOG with SQLAlchemy
# Copyright 2010 Pedro Algarvio <ufs@ufsoft.org>.

"""Sessions that persist in the database.

Every SESSION_CLEAN_FREQUENCY seconds, a pass is made over all persistant
sessions, and those that are more than PERSISTENT_SESSION_LIFETIME seconds old
are deleted. Transient sessions die after TRANSIENT_SESSION_LIFETIME seconds.

These three globals can be overridden by passing appropriate values to the
PersistentSessionWrapper constructor: sessionCleanFrequency, persistentSessionLifetime,
and transientSessionLifetime.
"""

import logging
from twisted.cred import checkers, credentials, error
from twisted.internet import defer
from twisted.internet.threads import deferToThread
from twisted.python import failure
from twisted.python.components import registerAdapter
from zope.interface import implements, Interface, Attribute

from nevow import guard
from ilog.database import db, Session, User

SESSION_CLEAN_FREQUENCY = 60 * 60 * 25  # 1 day, almost
PERSISTENT_SESSION_LIFETIME = 60 * 60 * 24 * 7 * 2 # 2 weeks
TRANSIENT_SESSION_LIFETIME = 60 * 12 + 32 # 12 minutes, 32 seconds.


log = logging.getLogger(__name__)

def usernameFromRequest(request):
    """
    Take a HTTP request and return a username of the form <user>@<domain>.

    @type request: L{inevow.IRequest}
    @param request: A HTTP request

    @return: A C{str}
    """
    username = request.args.get('username', [''])[0]
    if '@' not in username:
        username = '%s@%s' % (username, request.getHeader('host').split(':')[0])
    return username



class UsernamePassword(credentials.UsernamePassword):
    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (credentials.IUsernamePassword, )

    def checkPassword(self, password):
        log.debug("Authenticating %s", self.username)
        return self.user.authenticate(password)

    @db.sqla_session_inline_callbacks
    def requestAvatarId(self, sa_session=None):
        """Return the avatar id of the avatar which can be accessed using
        the given credentials.

        credentials will be an object with username and password attributes
        we need to raise an error to indicate failure or return a username
        to indicate success. requestAvatar will then be called with the avatar
        id we returned.
        """
        # check username
        yield log.debug("%s requestAvatarId of %s",
                        self.__class__.__name__, self.username)
        self.user = yield deferToThread(sa_session.query(User).get,
                                        self.username)
        if not self.user:
            yield log.debug("No user by the username: \"%s\"", self.username)
            raise failure.Failure(error.UnauthorizedLogin())

        matched = self.checkPassword(self.password)

        if sa_session.dirty:
            yield deferToThread(sa_session.commit)

        if not matched:
            yield log.warn("password didn't match for %s", self.username)
            raise failure.Failure(error.UnauthorizedLogin())
        defer.returnValue(self.username)

    def __repr__(self):
        return '<%s username="%s">' % (self.__class__.__name__, self.username)



class UsernamePasswordPreAuthenticated(UsernamePassword):

    def __init__(self, preauth):
        self.username = preauth.username
        self.password = None

    def checkPassword(self, password=None):
        log.debug("Passwordless Pre-Authenticating \"%s\"", self.username)
        return True


class AnonymousUserDefaults(object):

    defaults = {
        'username': 'anonymous',
        'items_per_page': 15,
        'is_admin': False,
        'show_adult_content': False
    }

    def to_dict(self):
        return self.defaults

class AuthenticatedUser(object):

    def __init__(self, db_user):
        for key, value in db_user.to_dict().iteritems():
            setattr(self, key, value)
        self.authenticated = True

    def __repr__(self):
        return '<%s "%s">' % (self.__class__.__name__, self.username)

class AnonymousUser(AuthenticatedUser):

    def __init__(self, db_user=AnonymousUserDefaults()):
        AuthenticatedUser.__init__(self, db_user)
        self.authenticated = False

@db.sqla_session_inline_callbacks
def ilog_mind_factory(request, creds, sa_session=None):
    if isinstance(creds, credentials.Anonymous):
        defer.returnValue(AnonymousUser())
    user = yield deferToThread(sa_session.query(User).get, creds.username)
    if not user:
        defer.returnValue(AnonymousUser())

    defer.returnValue(AuthenticatedUser(user))

class DBPassthrough(object):
    """A dictionaryish thing that manages sessions and interfaces with guard.

    This is set as the sessions attribute on a nevow.guard.SessionWrapper
    instance, or in this case, a subclass. Guard uses a vanilla dict by
    default; here we pretend to be a dict and introduce presistant-session
    behaviour.
    """
    def __init__(self, wrapper):
        self.wrapper = wrapper
        self._transientSessions = {}

    def __contains__(self, key):
        # we use __get__ here so that transient sessions are always created.
        # Otherwise, sometimes guard will call __contains__ and assume the
        # transient session is there, without creating it.
        try:
            self[key]
        except KeyError:
            return False
        return True

    has_key = __contains__

    def __getitem__(self, key):
#        log.debug('__getitem__ %s', key)
        if key is None:
            raise KeyError("None is not a valid session key")
        try:
            return self._transientSessions[key]
        except KeyError:
            if self.wrapper.authenticatedUserForKey(key):
                session = self.wrapper.sessionFactory(self.wrapper, key)
                self._transientSessions[key] = session
                session.setLifetime(self.wrapper.sessionLifetime) # screw you guard!
                session.checkExpired()
                return session
            raise

    def __setitem__(self, key, value):
#        log.debug('__setitem__ %s %s', key, value)
        self._transientSessions[key] = value

    def __delitem__(self, key):
#        log.debug('__delitem__ %s', key)
        del self._transientSessions[key]

    def __repr__(self):
        return 'DBPassthrough at %i; %r, with embelishments' % (
                                            id(self), self._transientSessions)


class PersistentSessionWrapper(guard.SessionWrapper):
    """
    Extends nevow.guard.SessionWrapper to re-authenticate previously
    authenticated users.

    There are 4 possible states:
    1) new user, no persistent session, no transient session
    2) anonymous user, no persistent session, transient session
    3) returning user, persistent session, no transient session
    4) active user, persistent session, transient session

    Guard will look it the sessions dict, and if it finds a key
    matching a cookie sent by the client, will return the value as the
    session. However, if a user has a persistent session cookie, but
    no transient session, one is created here.
    """
    def __init__(
        self,
        portal,
        transientSessionLifetime=TRANSIENT_SESSION_LIFETIME,
        persistentSessionLifetime=PERSISTENT_SESSION_LIFETIME,
        sessionCleanFrequency=SESSION_CLEAN_FREQUENCY,
        enableSubdomains=False,
        domains=(),
        **kw):
        """Initialize the PersistentSessionWrapper
        """
        if 'mindFactory' not in kw:
            kw['mindFactory'] = ilog_mind_factory
        guard.SessionWrapper.__init__(self, portal, **kw)
        self.sessions = DBPassthrough(self)
        self.cookieKey = 'ilog-user-cookie'
        self.sessionLifetime = transientSessionLifetime
        self.persistentSessionLifetime = persistentSessionLifetime
        self.sessionCleanFrequency = sessionCleanFrequency
        self._enableSubdomains = enableSubdomains
        self._domains = domains


    @db.sqla_session_inline_callbacks
    def createSessionForKey(self, key, username, sa_session=None):
        log.debug("Creating session for user %r with key: %r", username, key)
        session = yield deferToThread(sa_session.query(Session).get, key)
        if not session:
            session = Session(key)
            yield deferToThread(sa_session.add, session)
            user = yield deferToThread(sa_session.query(User).get, username)
            yield log.debug("Binding database user %r to session %r",
                            user, session)
            session.authenticated_as = user
            yield deferToThread(sa_session.commit)

    @db.sqla_session_inline_callbacks
    def authenticatedUserForKey(self, key, sa_session=None):
        log.debug("Querying for authenticated user with session key: %r", key)
        session = yield deferToThread(sa_session.query(Session).get, key)
        log.debug("Session found: %s", session)
        if session:
            log.debug("Renew'ing session...")
            session.renew()
            yield deferToThread(sa_session.commit)
            yield log.debug("Session's authenticated user: %s",
                            session.authenticated_as)
            defer.returnValue(session.authenticated_as)
        defer.returnValue(None)


    @db.sqla_session_inline_callbacks
    def removeSessionWithKey(self, key, sa_session=None):
        log.debug("Removing session with key: %r", key)
        session = yield deferToThread(sa_session.query(Session).get, key)
        if session:
            yield deferToThread(sa_session.delete, session)
            yield deferToThread(sa_session.commit)
        # if the session doesn't exist, we ignore that fact here.


    def cookieDomainForRequest(self, request):
        """
        Pick a domain to use when setting cookies.

        @type request: L{nevow.inevow.IRequest}
        @param request: Request to determine cookie domain for

        @rtype: C{str} or C{None}
        @return: Domain name to use when setting cookies, or C{None} to
            indicate that only the domain in the request should be used
        """
        log.debug("Grabing domain to use when setting cookies")
        host = request.getHeader('host')
        if host is None:
            # This is a malformed request that we cannot possibly handle
            # safely, fall back to the default behaviour.
            return None

        host = host.split(':')[0]
        for domain in self._domains:
            suffix = "." + domain
            if host == domain:
                # The request is for a domain which is directly recognized.
                if self._enableSubdomains:
                    # Subdomains are enabled, so the suffix is returned to
                    # enable the cookie for this domain and all its subdomains.
                    return suffix

                # Subdomains are not enabled, so None is returned to allow the
                # default restriction, which will enable this cookie only for
                # the domain in the request, to apply.
                return None

            if self._enableSubdomains and host.endswith(suffix):
                # The request is for a subdomain of a directly recognized
                # domain and subdomains are enabled.  Drop the unrecognized
                # subdomain portion and return the suffix to enable the cookie
                # for this domain and all its subdomains.
                return suffix

        if self._enableSubdomains:
            # No directly recognized domain matched the request.  If subdomains
            # are enabled, prefix the request domain with "." to make the
            # cookie valid for that domain and all its subdomains.  This
            # probably isn't extremely useful.  Perhaps it shouldn't work this
            # way.
            return "." + host

        # Subdomains are disabled and the domain from the request was not
        # recognized.  Return None to get the default behavior.
        return None


    def savorSessionCookie(self, request):
        """
        Make the session cookie last as long as the persistent session.

        @param request: The HTTP request object for the guard login URL.
        """
        cookieValue = request.getSession().uid

        log.debug("Making the session cookie last as long as the persistent "
                  "session: %r", cookieValue)

        request.addCookie(self.cookieKey, cookieValue, path='/',
                          max_age=self.persistentSessionLifetime,
                          domain=self.cookieDomainForRequest(request))


    @defer.inlineCallbacks
    def login(self, request, session, creds, segments):
        """Called to check the credentials of a user.

        Here we extend guard's implementation to pre-authenticate users
        if they have a valid persistent session.
        """
        log.debug("Checking credentials for creds: %r", creds)

        if isinstance(creds, credentials.Anonymous):
            preauth = yield self.authenticatedUserForKey(session.uid)
            yield log.debug("Pre-auth found: %s", preauth)
            if preauth is not None:
                log.debug("Found pre-authenticated creds: %r", preauth)
                yield self.savorSessionCookie(request)
                creds = yield UsernamePasswordPreAuthenticated(preauth)

        session.mind = yield self.mindFactory(request, creds)

        login_sucess = yield self.portal.login(
                creds, session.mind, self.credInterface).addCallback(
                    self._cbLoginSuccess, session, segments
                )

        if login_sucess:
            user = request.args.get('username')
            log.debug('Successful login of: %s', user)
            if user is not None:
                # create a database session and associate it with this user
                cookieValue = session.uid
                log.debug("Setting up cookie. UID: %s", cookieValue)
                if request.args.get('rememberMe'):
                    yield self.createSessionForKey(cookieValue, creds.username)
                    yield self.savorSessionCookie(request)
        defer.returnValue(login_sucess)

    @defer.inlineCallbacks
    def explicitLogout(self, session):
        """
        Here we override guard's behaviour for the logout action to
        delete the persistent session. In this case the user has
        explicitly requested a logout, so the persistent session must
        be deleted to require the user to log in on the next request.
        """
        yield log.debug("Explicitly logging out session: %r", session)
        yield guard.SessionWrapper.explicitLogout(self, session)
        yield self.removeSessionWithKey(session.uid)
        defer.returnValue(None)


    def getCredentials(self, request):
        """
        Override SessionWrapper.getCredentials to add the Host: header
        to the credentials.  This will make web-based virtual hosting
        work.
        """
        username = usernameFromRequest(request)
        password = request.args.get('password', [''])[0]
        return UsernamePassword(username, password)
