#  Copyright 2020 Vytautas Liuolia
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

from .session import RequestSession
from .util import ClosingStreamWrapper


class Manager:

    def __init__(self, engine, session_cls=RequestSession, binds=None):
        self._main_engine = engine
        self._engines = {engine: 'rw'}
        self._read_engines = (engine,)
        self._write_engines = (engine,)
        self._manager_get_bind = None

        self._binds = binds
        self._Session = sessionmaker(
            bind=engine, class_=session_cls, binds=binds)

        self.session_options = SessionOptions()

        assert not self._binds, 'passing custom binds is not supported yet'

    def _filter_by_role(self, engines, role):
        filtered = tuple(engine for engine in engines
                         if self._engines.get(engine) == role)
        return filtered or engines

    def add_engine(self, engine, role='r'):
        if role not in {'r', 'rw', 'w'}:
            raise ValueError("role must be one of ('r', 'rw', 'w')")

        self._engines[engine] = role
        if 'r' in role:
            self._read_engines += (engine,)
        if 'w' in role:
            self._write_engines += (engine,)

        if not self.session_options.read_from_rw_engines:
            self._read_engines = self._filter_by_role(
                self._read_engines, 'r')
        if not self.session_options.write_to_rw_engines:
            self._write_engines = self._filter_by_role(
                self._write_engines, 'w')

        # TODO (vytas): Do not tamper with custom binds.
        # if not self._binds:
        #     self._manager_get_bind = self.get_bind
        self._manager_get_bind = self.get_bind

    def get_bind(self, req, resp, session, mapper, clause):
        """
        Choose the appropriate bind for the given request session.
        """
        write = req.method not in self.session_options.safe_methods or (
            self.session_options.write_engine_if_flushing and
            session._flushing)
        engines = self._write_engines if write else self._read_engines

        if len(engines) == 1:
            return engines[0]

        if self.session_options.sticky_binds:
            return engines[hash(req.request_id) % len(engines)]

        return random.choice(engines)

    def get_session(self, req, resp):
        return self._Session(
            info={'req': req, 'resp': resp},
            _manager_get_bind=self._manager_get_bind)

    @property
    def read_engines(self):
        return self._read_engines

    @property
    def write_engines(self):
        return self._write_engines

    @contextlib.contextmanager
    def session_scope(self, req, resp):
        """
        Provide a transactional scope around a series of operations.
        """
        session = self.get_session(req, resp)

        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @property
    def middleware(self):
        return Middleware(self)


class Middleware:

    def __init__(self, manager):
        self._manager = manager
        self._options = manager.session_options

    def process_request(self, req, resp):
        """
        Set up the SQLAlchemy session for this request.

        The session object is stored as ``req.context.session``.
        """
        if req.method not in self._options.no_session_methods:
            req.context.session = self._manager.get_session(req, resp)
            if (self._options.sticky_binds and
                    not getattr(req.context, 'request_id', None)):
                req.request_id = self._options.request_id_func()
        else:
            req.context.session = None

    def process_response(self, req, resp, resource, req_succeeded):

        def cleanup():
            # NOTE(vytas): Break circular references between the request and
            #   the session.
            req.context.session = None
            del session.info['req']
            del session.info['resp']

            session.close()

        session = getattr(req.context, 'session', None)

        if session:
            try:
                if req_succeeded:
                    session.commit()
                else:
                    session.rollback()
            finally:
                if req_succeeded and resp.stream:
                    resp.stream = ClosingStreamWrapper(resp.stream, cleanup)
                else:
                    cleanup()


class SessionOptions:
    NO_SESSION_METHODS = frozenset(['OPTIONS', 'TRACE'])
    """HTTP methods that by default do not require a DB session."""

    SAFE_METHODS = frozenset(['GET', 'HEAD', 'OPTIONS', 'TRACE'])
    """
    HTTP methods that do not alter the server state.
    These methods are assumed to be fine with read-only replica engines.
    """

    def __init__(self):
        self.no_session_methods = self.NO_SESSION_METHODS
        self.safe_methods = self.SAFE_METHODS

        self.read_from_rw_engines = True
        self.write_to_rw_engines = True
        self.write_engine_if_flushing = True

        self.request_id_func = uuid.uuid4
        self.sticky_binds = False
