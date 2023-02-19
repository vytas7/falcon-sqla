import falcon
import falcon.asgi
import falcon.testing
import pytest
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import declarative_base

from falcon_sqla import Manager


class SpeedyDatabase:
    Base = declarative_base()

    class Object(Base):
        __tablename__ = 'objects'

        id = Column(Integer, primary_key=True)
        value = Column(String, nullable=False)

    def __init__(self):
        self.engine = None
        self.manager = None

    async def create_all(self):
        self.engine = create_async_engine('sqlite+aiosqlite://')
        self.manager = Manager(self.engine)

        async with self.engine.begin() as conn:
            await conn.run_sync(self.Base.metadata.create_all)

        async with self.manager.get_session() as session:
            async with session.begin():
                session.add_all([
                    self.Object(value='hello'),
                    self.Object(value='world'),
                    self.Object(value='123'),
                    self.Object(value=''),
                ])

            await session.commit()

    async def drop_all(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(self.Base.metadata.drop_all)


@pytest.fixture
def asyncdb():
    db = SpeedyDatabase()
    falcon.async_to_sync(db.create_all)

    yield db

    falcon.async_to_sync(db.drop_all)


class ObjectsResource:

    def __init__(self, db):
        self._db = db

    async def on_get(self, req, resp):
        statement = select(self._db.Object)

        results = await req.context.session.execute(statement)
        resp.media = [obj.value for obj in results.scalars()]

    async def on_get_stream(self, req, resp):
        statement = select(self._db.Object)

        # TODO: we cannot truly stream because we haven't implemented stream
        #   wrapper in middleware.py.
        text = ''
        result = await req.context.session.stream_scalars(statement)
        async for obj in result:
            text += f'{obj.value}\n'

        resp.text = text

    async def on_post(self, req, resp):
        media = await req.get_media()
        session = req.context.session

        session.add(self._db.Object(value=media.get('value', '')))
        await session.commit()

        resp.status = falcon.HTTP_CREATED


@pytest.fixture
def client(asyncdb):
    falcon.async_to_sync(asyncdb.create_all)

    app = falcon.asgi.App(middleware=[asyncdb.manager.middleware])

    obj_resource = ObjectsResource(asyncdb)
    app.add_route('/objects', obj_resource)
    app.add_route('/objects/stream', obj_resource, suffix='stream')

    return falcon.testing.TestClient(app)


def test_list_objects(client):
    resp = client.simulate_get('/objects')

    assert resp.status_code == 200
    assert set(resp.json) == {'', '123', 'hello', 'world'}


def test_stream_scalars(client):
    resp = client.simulate_get('/objects/stream')

    assert resp.status_code == 200
    assert set(resp.text.split()) == {'123', 'hello', 'world'}


def test_post_object(client):
    resp1 = client.simulate_post('/objects', json={'value': 'another'})
    assert resp1.status_code == 201

    resp2 = client.simulate_get('/objects')
    assert 'another' in resp2.json
