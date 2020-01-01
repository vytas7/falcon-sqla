
import falcon.testing
import pytest

from falcon_sqla import Manager


class Languages:

    def __init__(self, language_cls):
        self.language_cls = language_cls

    def on_get(self, req, resp):
        resp.media = [
            {
                'id': lang.id,
                'name': lang.name,
            }
            for lang in (
                req.context.session.query(self.language_cls)
                .order_by(self.language_cls.id)
            )]


@pytest.fixture
def client(base, engine):
    language_cls = base._decl_class_registry['Language']
    languages = Languages(language_cls)

    manager = Manager(engine())

    app = falcon.API(middleware=[manager.middleware])
    app.add_route('/languages', languages)

    return falcon.testing.TestClient(app)


def test_list_languages(client):
    resp = client.simulate_get('/languages')

    assert resp.status_code == 200
    assert resp.json == []
