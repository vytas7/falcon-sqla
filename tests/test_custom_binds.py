import falcon
import falcon.testing
import pytest
from sqlalchemy import create_engine

from falcon_sqla import Manager


class Languages:
    def __init__(self, database):
        misconfigured = create_engine('sqlite:////misconfigured')
        binds = {database.Language: database.read_engine}

        self.db = database
        self.manager = Manager(misconfigured, binds=binds)
        self.manager.session_options.read_from_rw_engines = False
        self.manager.add_engine(misconfigured, 'r')

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


@pytest.fixture
def client(create_app, database):
    languages = Languages(database)

    app = create_app()
    app.add_route('/languages', languages)

    return falcon.testing.TestClient(app)


def test_get_languages(client):
    resp = client.simulate_get('/languages')

    assert resp.status_code == 200
    assert resp.json == []
