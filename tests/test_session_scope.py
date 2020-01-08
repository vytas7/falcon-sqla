import falcon
import falcon.testing
import pytest

from falcon_sqla import Manager


class Languages:

    def __init__(self, database):
        self.db = database
        self.manager = Manager(database.write_engine)

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


@pytest.fixture
def client(database):
    def handle_exception(req, resp, ex, params):
        resp.status = falcon.HTTP_500
        resp.body = type(ex).__name__

    languages = Languages(database)

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
