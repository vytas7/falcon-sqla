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

from .middleware import Middleware
from .session import RequestSession


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

        # NOTE(vytas): Do not tamper with custom binds.
        if not self._binds:
            self._manager_get_bind = self.get_bind

    def get_bind(self, req, resp, session, mapper, clause):
        """Choose the appropriate bind for the given request session."""
        write = req.method not in self.session_options.safe_methods or (
            self.session_options.write_engine_if_flushing and
            session._flushing)
        engines = self._write_engines if write else self._read_engines

        if len(engines) == 1:
            return engines[0]

        if self.session_options.sticky_binds:
            return engines[hash(req.request_id) % len(engines)]

        return random.choice(engines)

    def get_session(self, req=None, resp=None):
        if req and resp:
            return self._Session(
                info={'req': req, 'resp': resp},
                _manager_get_bind=self._manager_get_bind)

        return self._Session()

    @property
    def read_engines(self):
        return self._read_engines

    @property
    def write_engines(self):
        return self._write_engines

    @contextlib.contextmanager
    def session_scope(self, req=None, resp=None):
        """
        Provide a transactional scope around a series of operations.

        Based on the ``session_scope()`` recipe from
        https://docs.sqlalchemy.org/orm/session_basics.html.
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
