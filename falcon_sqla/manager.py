#  Copyright 2020-2025 Vytautas Liuolia
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import contextlib
import random
import uuid

from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.sql import Delete
from sqlalchemy.sql import Update

from .constants import EngineRole
from .constants import SessionCleanup
from .middleware import Middleware
from .session import RequestSession

__all__ = ['Manager', 'SessionOptions']

CLOSE_ONLY = SessionCleanup.CLOSE_ONLY
COMMIT = SessionCleanup.COMMIT
COMMIT_ON_SUCCESS = SessionCleanup.COMMIT_ON_SUCCESS
ROLLBACK = SessionCleanup.ROLLBACK


class Manager:
    """A manager for SQLAlchemy sessions.

    This manager allows registering multiple SQLAlchemy engines, specifying
    if they are read-write or read-only or write-only capable.

    Args:
        engine (Engine): An instance of a SQLAlchemy Engine, usually obtained
            with its ``create_engine`` function. This engine is added as
            read-write.
        session_cls (type, optional): Session class used by this engine to
            create the session. Should be a subclass of SQLAlchemy ``Session``
            class. Defaults to :class:`~falcon_sqla.session.RequestSession`.
        binds (dict, optional): A dictionary that allows specifying custom
            binds on a per-entity basis in the session. See also
            https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.params.binds.
            Defaults to ``None``.
    """

    def __init__(self, engine, session_cls=RequestSession, binds=None):
        self._main_engine = engine
        self._engines = {engine: EngineRole.READ_WRITE}
        self._read_engines = (engine,)
        self._write_engines = (engine,)
        self._session_kwargs = {}

        self._binds = binds
        self._session_cls = session_cls
        self._Session = sessionmaker(
            bind=engine, class_=session_cls, binds=binds
        )

        self.session_options = SessionOptions()

    def _filter_by_role(self, engines, role):
        """Returns all the ``engines`` whose role is exactly ``role``.

        NOTE: if no engine with a role is found, all the engine are returned.
        """
        filtered = tuple(
            engine for engine in engines if self._engines.get(engine) == role
        )
        return filtered or engines

    def add_engine(self, engine, role=EngineRole.READ):
        """Adds a new engine with the specified role.

        Args:
            engine (Engine): An instance of a SQLAlchemy Engine.
            role (EngineRole): The role of the provided engine.
                Defaults to :attr:`~.EngineRole.READ`.

                Note:
                    In early versions of this library, `role` used to take
                    string values: ``'r'``, ``'w'``, ``'rw'``. These values
                    will continue to be supported in the foreseeable future for
                    backwards compatibility, but new code should prefer passing
                    enum constants instead.
        """
        role = EngineRole(role)

        self._engines[engine] = role
        if role in {EngineRole.READ, EngineRole.READ_WRITE}:
            self._read_engines += (engine,)
        if role in {EngineRole.WRITE, EngineRole.READ_WRITE}:
            self._write_engines += (engine,)

        if not self.session_options.read_from_rw_engines:
            self._read_engines = self._filter_by_role(
                self._read_engines, EngineRole.READ
            )
        if not self.session_options.write_to_rw_engines:
            self._write_engines = self._filter_by_role(
                self._write_engines, EngineRole.WRITE
            )

        # NOTE(vytas): Do not tamper with custom binds.
        # NOTE(vytas): We can only rely on RequestSession and its subclasses to
        #   implement the private _manager_get_bind constructor kwarg.
        if not self._binds and issubclass(self._session_cls, RequestSession):
            self._session_kwargs = {'_manager_get_bind': self.get_bind}

    def get_bind(self, req, resp, session, mapper, clause):
        """Choose the appropriate bind for the given request session.

        This method is not used directly, it's called by the session instance
        if multiple engines are defined.
        """
        write = req.method not in self.session_options.safe_methods or (
            self.session_options.write_engine_if_flushing
            and (session._flushing or isinstance(clause, (Update, Delete)))
        )
        engines = self._write_engines if write else self._read_engines

        if len(engines) == 1:
            return engines[0]

        if self.session_options.sticky_binds:
            return engines[hash(req.context.request_id) % len(engines)]

        return random.choice(engines)

    def get_session(self, req=None, resp=None):
        """Returns a new session object."""
        if req and resp:
            return self._Session(
                info={'req': req, 'resp': resp}, **self._session_kwargs
            )

        return self._Session()

    def close_session(self, session, succeeded, req=None, resp=None):
        """Close a session obtained via :func:`get_session`.

        .. note:: There is no need to invoke this method manually if you are
                  using the :func:`session_scope` context manager, or if you
                  are using middleware.
        """
        session_cleanup = self.session_options.session_cleanup
        attempt_commit = session_cleanup == COMMIT_ON_SUCCESS and succeeded

        try:
            if attempt_commit or session_cleanup == COMMIT:
                session.commit()
            elif session_cleanup != CLOSE_ONLY:
                session.rollback()
        except Exception:
            if attempt_commit:
                session.rollback()
            raise
        finally:
            if req and resp:
                # NOTE(vytas): Break circular references between the request
                #   and session in case the latter was stored in req.context.
                del session.info['req']
                del session.info['resp']
            session.close()

    @property
    def read_engines(self):
        """A tuple of read capable engines."""
        return self._read_engines

    @property
    def write_engines(self):
        """A tuple of write capable engines."""
        return self._write_engines

    @contextlib.contextmanager
    def session_scope(self, req=None, resp=None):
        """Provide a transactional scope around a series of operations.

        The session is obtained via :func:`get_sesion`, and finalized using
        :func:`close_session` upon exiting the context manager.

        Based on the ``session_scope()`` recipe from
        https://docs.sqlalchemy.org/orm/session_basics.html.
        """
        session = self.get_session(req, resp)
        succeeded = True

        try:
            yield session
        except Exception:
            succeeded = False
            raise
        finally:
            self.close_session(session, succeeded, req, resp)

    @property
    def middleware(self):
        """Create a new :class:`~falcon_sqla.middleware.Middleware` instance
        connected to this manager.
        """
        return Middleware(self)


class SessionOptions:
    """Defines a set of configurable options for the session.

    An instance of this class is exposed via :attr:`Manager.session_options`.

    Attributes:
        session_cleanup (SessionCleanup): Session cleanup mode; one of the
            :class:`~.SessionCleanup` constants.
            Defaults to :attr:`~.SessionCleanup.COMMIT_ON_SUCCESS`.
        no_session_methods (frozenset): HTTP methods that by default do not
            require a DB session. Defaults to
            :attr:`SessionOptions.NO_SESSION_METHODS`.
        safe_methods (frozenset): HTTP methods that can use a read-only engine
            since they do no alter the state of the db. Defaults to
            :attr:`SessionOptions.SAFE_METHODS`.
        read_from_rw_engines (bool): When True read operations are allowed from
            read-write engines. Only used if more than one engine is defined
            in the :class:`Manager`. Defaults to ``True``.
        write_to_rw_engines (bool): When True write operations are allowed from
            read-write engines. Only used if more than one engine is defined
            in the :class:`Manager`. Defaults to ``True``.
        write_engine_if_flushing (bool): When True a write engine is selected
            if the session is in flushing state. Only used if more than one
            engine is defined in the :class:`Manager`. Defaults to ``True``.
        sticky_binds (bool): When ``True``, the same engine will be used for
            each database operation for the same request. When ``False``, the
            engine will be chosen randomly from the ones with the required
            capabilities. Only used if more than one engine is defined in the
            :class:`Manager`. Defaults to ``False``.
        request_id_func (callable): A callable object that returns an unique
            id for to each session. The returned object must be hashable.
            Only used when :attr:`SessionOptions.sticky_binds` is ``True``.
            Defaults to ``uuid.uuid4``.
        wrap_response_stream (bool): When ``True`` (default), and the response
            stream is set, it is wrapped with an instance
            :class:`~falcon_sqla.util.ClosingStreamWrapper` in order to
            postpone SQLAlchemy session commit & cleanup after the response has
            finished streaming.
    """

    NO_SESSION_METHODS = frozenset(['OPTIONS', 'TRACE'])
    """HTTP methods that by default do not require a DB session."""

    SAFE_METHODS = frozenset(['GET', 'HEAD', 'OPTIONS', 'TRACE'])
    """
    HTTP methods that do not alter the server state.
    These methods are assumed to be fine with read-only replica engines.
    """

    __slots__ = [
        'session_cleanup',
        'no_session_methods',
        'safe_methods',
        'read_from_rw_engines',
        'write_to_rw_engines',
        'write_engine_if_flushing',
        'sticky_binds',
        'request_id_func',
        'wrap_response_stream',
    ]

    def __init__(self):
        self.session_cleanup = SessionCleanup.COMMIT_ON_SUCCESS

        self.no_session_methods = self.NO_SESSION_METHODS
        self.safe_methods = self.SAFE_METHODS

        self.read_from_rw_engines = True
        self.write_to_rw_engines = True
        self.write_engine_if_flushing = True

        self.sticky_binds = False
        self.request_id_func = uuid.uuid4

        self.wrap_response_stream = True
