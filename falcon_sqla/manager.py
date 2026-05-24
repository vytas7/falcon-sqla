#  Copyright 2020-2026 Vytautas Liuolia
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

from __future__ import annotations

from collections.abc import Hashable
import random
from types import TracebackType
from typing import Any, Callable, Optional, Union
import uuid

from falcon import Request
from falcon import Response
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
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
        session_cls (type): Synchronous session class used by this engine to
            create the session. Should be a subclass of SQLAlchemy ``Session``
            class. Defaults to :class:`~falcon_sqla.session.RequestSession` for
            synchronous engines.
        async_session_cls (type): Asynchronous session class used in the case
            the engine is asynchronous; ignored otherwise.
            Defaults to the vanilla ``AsyncSession``.
        binds (dict, optional): A dictionary that allows specifying custom
            binds on a per-entity basis in the session. See also
            https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.params.binds.
            Defaults to ``None``.
    """

    _middleware: Middleware | None
    _session_maker: sessionmaker[Any] | async_sessionmaker[Any]

    def __init__(
        self,
        engine: Engine | AsyncEngine,
        session_cls: type[Session] = RequestSession,
        async_session_cls: type[AsyncSession] = AsyncSession,
        binds: Optional[dict[Any, Any]] = None,
    ) -> None:
        self._main_engine = engine
        self._binds = binds
        self._engines: dict[Engine | AsyncEngine, EngineRole] = {
            engine: EngineRole.READ_WRITE
        }
        self._read_engines: tuple[Engine | AsyncEngine, ...] = (engine,)
        self._write_engines: tuple[Engine | AsyncEngine, ...] = (engine,)
        self._session_kwargs: dict[str, Any] = {}

        self._middleware = None
        self._uses_request_session = issubclass(session_cls, RequestSession)

        if isinstance(engine, AsyncEngine):
            self._is_async: bool = True
            self._session_maker = async_sessionmaker(
                bind=engine,
                class_=async_session_cls,
                sync_session_class=session_cls,
                binds=binds,
            )
        else:
            self._is_async = False
            session_cls = session_cls or RequestSession
            self._uses_request_session = issubclass(
                session_cls, RequestSession
            )
            self._session_maker = sessionmaker(
                bind=engine, class_=session_cls, binds=binds
            )

        self.session_options = SessionOptions()

    def _filter_by_role(
        self, engines: tuple[Engine | AsyncEngine, ...], role: EngineRole
    ) -> tuple[Engine | AsyncEngine, ...]:
        """Returns all the ``engines`` whose role is exactly ``role``.

        .. note::
            If no engine with a role is found, all the engines are returned.
        """
        filtered = tuple(
            engine for engine in engines if self._engines.get(engine) == role
        )
        return filtered or engines

    def add_engine(
        self,
        engine: Engine | AsyncEngine,
        role: Union[EngineRole, str] = EngineRole.READ,
    ) -> None:
        """Add a new engine with the specified role.

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
        if not self._binds and self._uses_request_session:
            self._session_kwargs = {'_manager_get_bind': self.get_bind}

    def get_bind(
        self,
        req: Request,
        resp: Response,
        session: Session,
        mapper: Any,
        clause: Any,
    ) -> Engine | AsyncEngine:
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

    def get_session(
        self, req: Request | None = None, resp: Response | None = None
    ) -> Session | AsyncSession:
        """Returns a new session object."""
        if req and resp:
            return self._session_maker(  # type: ignore[no-any-return]
                info={'req': req, 'resp': resp},
            )

        return self._session_maker()  # type: ignore[no-any-return]

    def close_session(
        self,
        session: Session,
        succeeded: bool,
        req: Request | None = None,
        resp: Response | None = None,
    ) -> None:
        """Close a session obtained via :func:`get_session`.

        .. note::
            There is no need to invoke this method manually if you are using
            the :func:`session_scope` context manager, or if you are using
            :attr:`middleware`.
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

    async def close_session_async(
        self,
        session: AsyncSession,
        succeeded: bool,
        req: Request | None = None,
        resp: Response | None = None,
    ) -> None:
        """Close an async session obtained via :func:`get_session`.

        .. note::
            There is no need to invoke this method manually if you are using
            the :func:`session_scope` context manager, or if you are using
            :attr:`middleware`.
        """
        session_cleanup = self.session_options.session_cleanup
        attempt_commit = session_cleanup == COMMIT_ON_SUCCESS and succeeded

        try:
            if attempt_commit or session_cleanup == COMMIT:
                await session.commit()
            elif session_cleanup != CLOSE_ONLY:
                await session.rollback()
        except Exception:
            if attempt_commit:
                await session.rollback()
            raise
        finally:
            if req and resp:
                # NOTE(vytas): Break circular references between the request
                #   and session in case the latter was stored in req.context.
                del session.info['req']
                del session.info['resp']
            await session.close()

    @property
    def read_engines(self) -> tuple[Engine | AsyncEngine, ...]:
        """A tuple of read capable engines."""
        return self._read_engines

    @property
    def write_engines(self) -> tuple[Engine | AsyncEngine, ...]:
        """A tuple of write capable engines."""
        return self._write_engines

    def session_scope(
        self,
        req: Optional[Request] = None,
        resp: Optional[Response] = None,
    ) -> _SessionScope:
        """Provide a transactional scope around a series of operations.

        The session is obtained via :func:`get_session`, and finalized using
        :func:`close_session` (or :func:`close_session_async`, for an async
        manager) upon exiting the context manager.

        Use as a regular context manager for a sync :class:`Manager`::

            with manager.session_scope() as session:
                ...

        and as an async context manager for one wrapping an
        :class:`~sqlalchemy.ext.asyncio.AsyncEngine`::

            async with manager.session_scope() as session:
                ...

        Mixing the two will raise a :exc:`TypeError`.

        Based on the ``session_scope()`` recipe from
        https://docs.sqlalchemy.org/orm/session_basics.html.
        """
        return _SessionScope(self, req, resp)

    @property
    def middleware(self) -> Middleware:
        """Create a :class:`~falcon_sqla.middleware.Middleware` instance
        connected to this manager.

        .. note::
            The middleware component is instantiated only once.
            Subsequent access to this property will return the same
            (cached) instance.
        """
        if self._middleware is None:
            self._middleware = Middleware(self)
        return self._middleware


class _SessionScope:
    """Sync/async context manager returned by :meth:`Manager.session_scope`.

    Implements both the synchronous and the asynchronous context manager
    protocols, dispatching to :meth:`Manager.close_session` or
    :meth:`Manager.close_session_async` depending on the form actually
    used (``with`` vs. ``async with``).

    Using the wrong form for the underlying engine raises a
    :exc:`TypeError` with a hint about the right one.
    """

    def __init__(
        self,
        manager: Manager,
        req: Optional[Request] = None,
        resp: Optional[Response] = None,
    ) -> None:
        self._manager = manager
        self._req = req
        self._resp = resp
        self._sync_session: Session | None = None
        self._async_session: AsyncSession | None = None

    def __enter__(self) -> Session:
        if self._manager._is_async:
            raise TypeError(
                'this Manager wraps an async engine; '
                'use `async with manager.session_scope(...) as session:` '
                'instead of `with`'
            )
        session = self._manager.get_session(self._req, self._resp)
        assert isinstance(session, Session)
        self._sync_session = session
        return session

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        assert self._sync_session is not None
        self._manager.close_session(
            self._sync_session, exc_type is None, self._req, self._resp
        )

    async def __aenter__(self) -> AsyncSession:
        if not self._manager._is_async:
            raise TypeError(
                'this Manager wraps a synchronous engine; '
                'use `with manager.session_scope(...) as session:` '
                'instead of `async with`'
            )
        session = self._manager.get_session(self._req, self._resp)
        assert isinstance(session, AsyncSession)
        self._async_session = session
        return session

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        assert self._async_session is not None
        await self._manager.close_session_async(
            self._async_session, exc_type is None, self._req, self._resp
        )


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

    session_cleanup: SessionCleanup
    no_session_methods: frozenset[str]
    safe_methods: frozenset[str]
    read_from_rw_engines: bool
    write_to_rw_engines: bool
    write_engine_if_flushing: bool
    sticky_binds: bool
    request_id_func: Callable[[], Hashable]
    wrap_response_stream: bool

    def __init__(self) -> None:
        self.session_cleanup = SessionCleanup.COMMIT_ON_SUCCESS

        self.no_session_methods = self.NO_SESSION_METHODS
        self.safe_methods = self.SAFE_METHODS

        self.read_from_rw_engines = True
        self.write_to_rw_engines = True
        self.write_engine_if_flushing = True

        self.sticky_binds = False
        self.request_id_func = uuid.uuid4

        self.wrap_response_stream = True
