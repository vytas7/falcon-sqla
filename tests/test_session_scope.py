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


@pytest.fixture
def client(base, engine):
    language_cls = base._decl_class_registry['Language']
    languages = Languages(engine(), language_cls)

    app = falcon.API()
    app.add_route('/languages', languages)

    return falcon.testing.TestClient(app)


def test_list_languages(client):
    resp = client.simulate_get('/languages')

    assert resp.status_code == 200
    assert resp.json == []
