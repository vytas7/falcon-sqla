import io

import falcon
import falcon.testing
import pytest

from falcon_sqla import Manager


class Languages:

    def __init__(self, db):
        self.db = db

    def on_get(self, req, resp):
        resp.media = [
            {
                'id': lang.id,
                'name': lang.name,
                'created': lang.created,
            }
            for lang in (
                req.context.session.query(self.db.Language)
                .order_by(self.db.Language.created)
            )]

    def on_get_names(self, req, resp):
        def stream_names():
            for lang in (
                req.context.session.query(self.db.Language)
                .order_by(self.db.Language.id)
            ):
                yield lang.name.encode()
                yield b'\n'

        resp.context_type = falcon.MEDIA_TEXT

        if req.get_param_as_bool('zero_division'):
            resp.media = 0/0

        if req.get_param_as_bool('filelike'):
            resp.stream = io.BytesIO(b''.join(stream_names()))
        elif req.get_param_as_bool('iterable_as_stream'):
            resp.stream = iter(tuple(stream_names()))
        else:
            resp.stream = stream_names()

    def on_post(self, req, resp):
        language = self.db.Language(
            name=req.media['name'], created=req.media.get('created'))
        req.context.session.add(language)
        resp.status = falcon.HTTP_CREATED

    def on_options(self, req, resp):
        resp.content_length = 0
        resp.status = falcon.HTTP_OK

        resp.set_header('Allow', 'OPTIONS, GET, POST')
        resp.set_header('X-Req-Session-Is-None',
                        str(req.context.session is None))


@pytest.fixture(params=['sticky_binds: no', 'sticky_binds: yes'])
def client(request, create_app, database):
    def handle_exception(req, resp, ex, params):
        resp.status = falcon.HTTP_500
        resp.media = {'error': type(ex).__name__}

    languages = Languages(database)

    manager = Manager(database.write_engine)
    manager.add_engine(database.read_engine, 'r')
    manager.session_options.sticky_binds = request.param.endswith('yes')

    app = create_app(middleware=[manager.middleware])
    app.add_route('/languages', languages)
    app.add_route('/names', languages, suffix='names')
    app.add_error_handler(Exception, handle_exception)

    return falcon.testing.TestClient(app)


@pytest.fixture()
def tunable_client(create_app, database):
    def create(options):
        manager = Manager(database.write_engine)
        manager.add_engine(database.read_engine, 'r')
        for key, value in options.items():
            setattr(manager.session_options, key, value)

        languages = Languages(database)

        app = create_app(middleware=[manager.middleware])
        app.add_route('/languages', languages)
        app.add_route('/names', languages, suffix='names')

        return falcon.testing.TestClient(app)

    return create


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
    assert resp.json == {'error': 'ZeroDivisionError'}


def test_options(client):
    resp = client.simulate_options('/languages')

    assert resp.status_code == 200
    assert resp.headers['X-Req-Session-Is-None'] == 'True'


@pytest.mark.parametrize('wrap_stream', [True, False])
@pytest.mark.parametrize('use_file_wrapper', [True, False])
def test_wrap_response_stream(tunable_client, wrap_stream, use_file_wrapper):
    def file_wrapper(obj, ignored_size=None):
        size = 3
        while True:
            chunk = obj.read(size)
            if not chunk:
                break
            history.append(chunk)
            yield chunk
            size += 1

    history = []

    client = tunable_client({'wrap_response_stream': wrap_stream})
    wrapper = file_wrapper if use_file_wrapper else None

    client.simulate_post('/languages',
                         json={'name': 'Python', 'created': 1991})
    client.simulate_post('/languages',
                         json={'name': 'Rust', 'created': 2010})
    client.simulate_post('/languages',
                         json={'name': 'PHP', 'created': 1994})

    resp = client.simulate_get('/names?filelike', file_wrapper=wrapper)
    assert resp.status_code == 200
    assert resp.text == 'Python\nRust\nPHP\n'

    if use_file_wrapper:
        assert history == [b'Pyt', b'hon\n', b'Rust\n', b'PHP\n']
    else:
        assert history == []
