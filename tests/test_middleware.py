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

        if req.get_param_as_bool('zero_division'):
            resp.body = str(0/0)

        if req.get_param_as_bool('iterable_as_stream'):
            resp.stream = iter(tuple(stream_names()))
        else:
            resp.stream = stream_names()

    def on_post(self, req, resp):
        language = self.language_cls(
            name=req.media['name'], created=req.media.get('created'))
        req.context.session.add(language)
        resp.status = falcon.HTTP_CREATED

    def on_options(self, req, resp):
        resp.content_length = 0
        resp.status = falcon.HTTP_OK

        resp.set_header('Allow', 'OPTIONS, GET, POST')
        resp.set_header('X-Req-Session-Is-None',
                        str(req.context.session is None))


@pytest.fixture
def client(base, create_engines):
    def handle_exception(req, resp, ex, params):
        resp.status = falcon.HTTP_500
        resp.body = type(ex).__name__

    language_cls = base._decl_class_registry['Language']
    languages = Languages(language_cls)

    engines = create_engines()
    manager = Manager(engines['write'])
    manager.add_engine(engines['read'], 'r')

    app = falcon.API(middleware=[manager.middleware])
    app.add_route('/languages', languages)
    app.add_route('/names', languages, suffix='names')
    app.add_error_handler(Exception, handle_exception)

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
    assert resp2.status_code == 200
    assert resp2.text == 'Python\nRust\nPHP\n'

    resp3 = client.simulate_get('/names?iterable_as_stream')
    assert resp3.text == resp2.text


def test_rollback(client):
    resp = client.simulate_get('/names?zero_division')
    assert resp.status_code == 500
    assert resp.text == 'ZeroDivisionError'


def test_options(client):
    resp = client.simulate_options('/languages')

    assert resp.status_code == 200
    assert resp.headers['X-Req-Session-Is-None'] == 'True'
