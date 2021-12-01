import falcon
import falcon.asgi
import falcon.testing
import pytest
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import select

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

    # def drop_all(self):
    #     self.Base.metadata.create_all(self.write_engine)


@pytest.fixture
def asyncdb():
    return SpeedyDatabase()


class ObjectsResource:

    def __init__(self, db):
        self._db = db

    async def on_get(self, req, resp):
        query = select(self._db.Object)

        results = await req.context.session.execute(query)
        resp.media = [obj.value for obj in results.scalars()]


@falcon.runs_sync
# Same shit with pytest.mark.asyncio
async def test_list_objects(asyncdb):
    await asyncdb.create_all()

    app = falcon.asgi.App(middleware=[asyncdb.manager.middleware])
    app.add_route('/objects', ObjectsResource(asyncdb))

    # client = falcon.testing.TestClient(app)

    # Fails with RuntimeError: This event loop is already running
    # Probably because we have dropped into another greenlet stack
    # resp = client.simulate_get('/objects')

    async with falcon.testing.ASGIConductor(app) as conductor:
        resp = await conductor.simulate_get('/objects')

        assert resp.status_code == 200
        assert set(resp.json) == {'', '123', 'hello', 'world'}
