import falcon
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
                'created': lang.created,
            }
            for lang in (
                req.context.session.query(self.language_cls)
                .order_by(self.language_cls.created)
            )]

    def on_get_names(self, req, resp):
        def stream_names():
            for lang in (
                req.context.session.query(self.language_cls)
                .order_by(self.language_cls.id)
            ):
                yield lang.name.encode()
                yield b'\n'

        resp.context_type = falcon.MEDIA_TEXT
        resp.stream = stream_names()

    def on_post(self, req, resp):
        language = self.language_cls(
            name=req.media['name'], created=req.media.get('created'))
        req.context.session.add(language)
        resp.status = falcon.HTTP_CREATED


@pytest.fixture
def client(base, create_engines):
    language_cls = base._decl_class_registry['Language']
    languages = Languages(language_cls)

    engines = create_engines()
    manager = Manager(engines['write'])
    manager.add_engine(engines['read'], 'r')

    app = falcon.API(middleware=[manager.middleware])
    app.add_route('/languages', languages)
    app.add_route('/names', languages, suffix='names')

    return falcon.testing.TestClient(app)


def test_list_languages(client):
    resp = client.simulate_get('/languages')

    assert resp.status_code == 200
    assert resp.json == []


def test_post_languages(client):
    client.simulate_post('/languages',
                         json={'name': 'Python', 'created': 1991})
    client.simulate_post('/languages',
                         json={'name': 'Rust', 'created': 2010})
    client.simulate_post('/languages',
                         json={'name': 'PHP', 'created': 1994})

    resp1 = client.simulate_get('/languages')
    assert resp1.json == [
        {'created': 1991, 'id': 1, 'name': 'Python'},
        {'created': 1994, 'id': 3, 'name': 'PHP'},
        {'created': 2010, 'id': 2, 'name': 'Rust'},
    ]

    resp2 = client.simulate_get('/names')
    assert resp2.text == 'Python\nRust\nPHP\n'
