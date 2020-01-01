import contextlib

from sqlalchemy.orm.session import sessionmaker

from .session import RequestSession


class Manager:

    def __init__(self, engine, session_cls=RequestSession):
        self._engine = engine
        self.Session = sessionmaker(bind=engine, class_=session_cls)

    def get_session(self, req, resp):
        return self.Session()

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

    def process_request(self, req, resp):
        """
        Set up the SQLAlchemy session for this request.

        The session object is stored as ``req.context.session``.
        """
        req.context.session = self._manager.get_session(req, resp)

    def process_response(self, req, resp, resource, req_succeeded):
        session = getattr(req.context, 'session')

        if session:
            # NOTE(vytas): Break circular references between the request and
            #   the session, if any.
            req.context.session = None

            try:
                if req_succeeded:
                    session.commit()
                else:
                    session.rollback()
            finally:
                session.close()
