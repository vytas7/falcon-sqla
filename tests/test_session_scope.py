import falcon
import falcon.testing
import pytest
from sqlalchemy.orm.session import Session

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
                        session.query(self.db.Language)
                        .order_by(self.db.Language.id)
                )]

            if req.get_param_as_bool('zero_division'):
                resp.body = str(0/0)


@pytest.fixture(params=[RequestSession, Session, FunkySession])
def client(request, database):
    def handle_exception(req, resp, ex, params):
        resp.status = falcon.HTTP_500
        resp.body = type(ex).__name__

    languages = Languages(database, session_cls=request.param)

    app = falcon.API()
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
    assert resp.text == 'ZeroDivisionError'


def test_generic_scope(database):
    manager = Manager(database.write_engine)

    with manager.session_scope() as session:
        session.add(database.Language(name='Malbolge', created=1998))

    with manager.session_scope() as session:
        malbolge = session.query(database.Language).first()
        assert malbolge.name == 'Malbolge'
        assert malbolge.created == 1998
