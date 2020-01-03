import falcon
import falcon.testing
import pytest

from falcon_sqla import Manager


class Languages:

    def __init__(self, engine, language_cls):
        self.manager = Manager(engine)
        self.language_cls = language_cls

    def on_get(self, req, resp):
        with self.manager.session_scope(req, resp) as session:
            resp.media = [
                {
                    'id': lang.id,
                    'name': lang.name,
                }
                for lang in (
                        session.query(self.language_cls)
                        .order_by(self.language_cls.id)
                )]

            if req.get_param_as_bool('zero_division'):
                resp.body = str(0/0)


@pytest.fixture
def client(base, create_engines):
    def handle_exception(req, resp, ex, params):
        resp.status = falcon.HTTP_500
        resp.body = type(ex).__name__

    engines = create_engines()

    language_cls = base._decl_class_registry['Language']
    languages = Languages(engines['write'], language_cls)

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
