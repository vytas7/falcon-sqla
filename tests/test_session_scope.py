import falcon
import falcon.testing
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.session import Session

from falcon_sqla.manager import SessionCleanup
from falcon_sqla.manager import Manager
from falcon_sqla.session import RequestSession


class FunkySession(Session):
    pass


class Languages:
    def __init__(self, database, session_cls):
        self.db = database
        self.manager = Manager(database.write_engine, session_cls=session_cls)

    def on_get(self, req, resp):
        with self.manager.session_scope(req, resp) as session:
            resp.media = [
                {
                    'id': lang.id,
                    'name': lang.name,
                }
                for lang in (
                    session.query(self.db.Language).order_by(
                        self.db.Language.id
                    )
                )
            ]

            if req.get_param_as_bool('zero_division'):
                resp.media = 0 / 0


@pytest.fixture(params=[RequestSession, Session, FunkySession])
def client(request, create_app, database):
    def handle_exception(req, resp, ex, params):
        resp.status = falcon.HTTP_500
        resp.media = {'error': type(ex).__name__}

    languages = Languages(database, session_cls=request.param)

    app = create_app()
    app.add_route('/languages', languages)
    app.add_error_handler(Exception, handle_exception)

    return falcon.testing.TestClient(app)


def test_list_languages(client):
    resp = client.simulate_get('/languages')

    assert resp.status_code == 200
    assert resp.json == []


def test_rollback(client):
    resp = client.simulate_get('/languages?zero_division')
    assert resp.status_code == 500
    assert resp.json == {'error': 'ZeroDivisionError'}


def test_generic_scope(database):
    manager = Manager(database.write_engine)

    with manager.session_scope() as session:
        session.add(database.Language(name='Malbolge', created=1998))

    with manager.session_scope() as session:
        malbolge = session.query(database.Language).first()
        assert malbolge.name == 'Malbolge'
        assert malbolge.created == 1998


@pytest.mark.parametrize(
    'cleanup,expected',
    [
        (SessionCleanup.CLOSE_ONLY, 1999),
        (SessionCleanup.COMMIT, 1998),
        (SessionCleanup.COMMIT_ON_SUCCESS, 1998),
        (SessionCleanup.ROLLBACK, 1999),
    ],
)
def test_session_cleanup(database, cleanup, expected):
    manager = Manager(database.write_engine)
    manager.session_options.session_cleanup = cleanup

    with manager.session_scope() as session:
        session.add(database.Language(name='Malbolge', created=1998 + 1))
        session.commit()

    with manager.session_scope() as session:
        malbolge = session.query(database.Language).first()
        malbolge.created = 1998

    with manager.session_scope() as session:
        malbolge = session.query(database.Language).first()
        assert malbolge.created == expected


@pytest.mark.parametrize(
    'cleanup,expected',
    [
        (SessionCleanup.CLOSE_ONLY, 1999),
        (SessionCleanup.COMMIT, 1998),
        (SessionCleanup.COMMIT_ON_SUCCESS, 1999),
        (SessionCleanup.ROLLBACK, 1999),
    ],
)
def test_close_on_error(database, cleanup, expected):
    manager = Manager(database.write_engine)
    manager.session_options.session_cleanup = cleanup

    with manager.session_scope() as session:
        session.add(database.Language(name='Malbolge', created=1998 + 1))
        session.commit()

    with pytest.raises(ZeroDivisionError):
        with manager.session_scope() as session:
            malbolge = session.query(database.Language).first()
            malbolge.created = 1998
            malbolge.statement = 0 / 0

    with manager.session_scope() as session:
        malbolge = session.query(database.Language).first()
        assert malbolge.created == expected


@pytest.mark.parametrize(
    'cleanup,expected',
    [
        (SessionCleanup.COMMIT, 1998),
        (SessionCleanup.COMMIT_ON_SUCCESS, 1999),
    ],
)
def test_close_error_on_commit(database, cleanup, expected):
    manager = Manager(database.write_engine)
    manager.session_options.session_cleanup = cleanup

    with manager.session_scope() as session:
        malbolge = database.Language(name='Malbolge', created=1998)
        session.add(malbolge)
        session.commit()
        idn = malbolge.id

    with pytest.raises(IntegrityError):
        with manager.session_scope() as session:
            session.add(database.Language(id=idn, name='Error', created=2525))
