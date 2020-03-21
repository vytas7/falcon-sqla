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

from .util import ClosingStreamWrapper


class Middleware:
    """Falcon middleware that can be used with the session manager.

    Args:
        manager (Manager): Manager instance to use in this middleware.
    """
    def __init__(self, manager):
        self._manager = manager
        self._options = manager.session_options

    def process_request(self, req, resp):
        """
        Set up the SQLAlchemy session for this request.

        The session object is stored as ``req.context.session``.
        When the option :attr:`SessionOptions.sticky_binds` is set to True an
        identification of the request is stored in ``req.context.request_id``
        (if not already present).
        """
        if req.method not in self._options.no_session_methods:
            req.context.session = self._manager.get_session(req, resp)
            if (self._options.sticky_binds and
                    not getattr(req.context, 'request_id', None)):
                req.context.request_id = self._options.request_id_func()
        else:
            req.context.session = None

    def process_response(self, req, resp, resource, req_succeeded):
        """
        Cleans up the session if one was provided.

        Finalizes the session by calling commit if `req_succeeded` is True,
        rollback otherwise. Finally it will close the session.
        """
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
