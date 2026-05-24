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

import functools
from typing import Optional, TYPE_CHECKING

from .util import ClosingStreamWrapper

if TYPE_CHECKING:
    from falcon import Request
    from falcon import Response
    from falcon.asgi import Request as AsyncRequest
    from falcon.asgi import Response as AsyncResponse

    from .manager import Manager


class Middleware:
    """Falcon middleware that can be used with the session manager.

    Args:
        manager (Manager): Manager instance to use in this middleware.
    """

    def __init__(self, manager: Manager) -> None:
        self._manager = manager
        self._options = manager.session_options

    def process_request(self, req: Request, resp: Response) -> None:
        """
        Set up a SQLAlchemy session for this request.

        The session object is stored as ``req.context.session``.

        When the :attr:`~.SessionOptions.sticky_binds` option is set to
        ``True``, a ``req.context.request_id`` identifier is created (if not
        already present) by calling the
        :attr:`~.SessionOptions.request_id_func` function.
        """
        if req.method not in self._options.no_session_methods:
            req.context.session = self._manager.get_session(req, resp)
            if self._options.sticky_binds and not getattr(
                req.context, 'request_id', None
            ):
                req.context.request_id = self._options.request_id_func()
        else:
            req.context.session = None

    async def process_request_async(
        self, req: AsyncRequest, resp: AsyncResponse
    ) -> None:
        self.process_request(req, resp)

    def process_response(
        self,
        req: Request,
        resp: Response,
        resource: Optional[object],
        req_succeeded: bool,
    ) -> None:
        """
        Clean up the session, if one was provided.

        This response hook finalizes the session by calling the manager's
        :func:`~falcon_sqla.Manager.close_session` method.
        """
        session = getattr(req.context, 'session', None)

        if session:
            if resp.stream is not None and self._options.wrap_response_stream:
                resp.stream = ClosingStreamWrapper(
                    resp.stream,
                    functools.partial(
                        self._manager.close_session,
                        session,
                        req_succeeded,
                        req,
                        resp,
                    ),
                )
            else:
                self._manager.close_session(session, req_succeeded, req, resp)

    async def process_response_async(
        self,
        req: AsyncRequest,
        resp: AsyncResponse,
        resource: Optional[object],
        req_succeeded: bool,
    ) -> None:
        """
        Clean up the session, if one was provided.

        This response hook finalizes the session by calling the manager's
        :func:`~falcon_sqla.Manager.close_session_async` method.
        """
        session = getattr(req.context, 'session', None)

        if session is not None:
            if resp.stream is not None:
                resp.schedule(
                    functools.partial(
                        self._manager.close_session_async,
                        session,
                        req_succeeded,
                        req,
                        resp,
                    )
                )
            else:
                await self._manager.close_session_async(
                    session, req_succeeded, req, resp
                )
