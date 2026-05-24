#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import json
import pathlib
import sys
from typing import Any

import falcon
import falcon.asgi
from falcon.asgi import Request
from falcon.asgi import Response
from sqlalchemy import event
from sqlalchemy import ForeignKey
from sqlalchemy import select
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import MappedAsDataclass
from sqlalchemy.orm import relationship
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import ConnectionPoolEntry

import falcon_sqla

HERE = pathlib.Path(__file__).resolve().parent
DATA_PATH = HERE / 'solar_system.json'
DATABASE_PATH = HERE / 'solar_async.sqlite'
DATABASE_URL = f'sqlite+aiosqlite:///{DATABASE_PATH}'


class Base(MappedAsDataclass, DeclarativeBase, kw_only=True):
    pass


class CelestialBody(Base):
    __abstract__ = True

    name: Mapped[str] = mapped_column(primary_key=True)

    mass: Mapped[float]
    radius: Mapped[float]
    distance: Mapped[float | None]  # to be precise, it is semi-major axis

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name.title(),
            'mass': self.mass,
            'radius': self.radius,
            'distance': self.distance,
        }


class Star(CelestialBody):
    __tablename__ = 'stars'


class PlanetaryBody(CelestialBody):
    __tablename__ = 'planets'

    kind: Mapped[str] = mapped_column(init=False)
    satellites: Mapped[list['Satellite']] = relationship(
        order_by='Satellite.distance',
        init=False,
        default_factory=list,
    )

    __mapper_args__ = {
        'polymorphic_on': 'kind',
        'polymorphic_abstract': True,
    }

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            'satellites': [s.name.title() for s in self.satellites],
        }


class Planet(PlanetaryBody):
    __mapper_args__ = {'polymorphic_identity': 'planet'}


class DwarfPlanet(PlanetaryBody):
    __mapper_args__ = {'polymorphic_identity': 'dwarf_planet'}


class Satellite(CelestialBody):
    __tablename__ = 'satellites'

    primary: Mapped[str] = mapped_column(ForeignKey('planets.name'))

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), 'primary': self.primary.title()}


_KINDS = {
    f'{model.__name__.lower()}s': model
    for model in (Star, Planet, DwarfPlanet, Satellite)
}


class BodyResource:
    def __init__(self, model: type[CelestialBody]) -> None:
        self._model = model
        # Async sessions can't lazy-load, so eager-load satellites for the
        # polymorphic planet/dwarf-planet collection that uses them.
        self._eager: list[Any] = (
            [selectinload(PlanetaryBody.satellites)]
            if issubclass(model, PlanetaryBody)
            else []
        )

    async def on_get_collection(self, req: Request, resp: Response) -> None:
        stmt = (
            select(self._model)
            .order_by(self._model.distance)
            .options(*self._eager)
        )
        result = await req.context.session.execute(stmt)
        resp.media = [body.to_dict() for body in result.scalars()]

    async def on_get(self, req: Request, resp: Response, name: str) -> None:
        session: AsyncSession = req.context.session
        body = await session.get(
            self._model, name.lower(), options=self._eager
        )
        if body is None:
            raise falcon.HTTPNotFound()
        resp.media = body.to_dict()

    async def on_put(self, req: Request, resp: Response, name: str) -> None:
        if self._model is Star:
            # solar_sync.py uses HTTP_799 for fun, but ASGI servers look
            # up status phrases by the numeric code, so we stick with a
            # registered one here.
            raise falcon.HTTPError(
                falcon.HTTP_UNPROCESSABLE_ENTITY,
                description='You cannot change the Sun, or add stars!',
            )

        name = name.lower()
        media = await req.get_media()
        media.pop('name', None)
        if 'primary' in media:
            media['primary'] = media['primary'].lower()

        session: AsyncSession = req.context.session
        body = await session.get(self._model, name, options=self._eager)
        if body is None:
            body = self._model(name=name, **media)
            session.add(body)
            resp.status = falcon.HTTP_CREATED
        else:
            for key, value in media.items():
                setattr(body, key, value)
            resp.status = falcon.HTTP_OK
        resp.media = body.to_dict()


async def init_engine(url: str, fresh: bool = False) -> AsyncEngine:
    engine = create_async_engine(url)

    # SQLAlchemy events are sync-only, so attach to the underlying sync_engine.
    @event.listens_for(engine.sync_engine, 'connect')
    def _sqlite_enable_foreign_keys(
        dbapi_connection: DBAPIConnection, _: ConnectionPoolEntry
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')
        cursor.close()

    if fresh:
        print(f'Initializing new database: {engine.url}')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Seed with data from solar_system.json
        async with AsyncSession(engine) as session:
            data = json.loads(DATA_PATH.read_text())
            for kind, items in data.items():
                for item in items:
                    item = {**item, 'name': item['name'].lower()}
                    if 'primary' in item:
                        item['primary'] = item['primary'].lower()
                    session.add(_KINDS[kind](**item))
            await session.commit()
    else:
        print(f'Using existing database: {engine.url}')

    # Drop the pool so Uvicorn's event loop opens fresh connections, even in
    # the case this method is run separately via asyncio.run().
    await engine.dispose()

    return engine


def create_app(
    manager: falcon_sqla.Manager,
) -> falcon.asgi.App[Request, Response]:
    app: falcon.asgi.App[Request, Response] = falcon.asgi.App(
        middleware=[manager.middleware]
    )
    for kind, model in _KINDS.items():
        resource = BodyResource(model)
        app.add_route(f'/{kind}', resource, suffix='collection')
        app.add_route(f'/{kind}/{{name}}', resource)

    return app


if __name__ == '__main__':
    engine = asyncio.run(init_engine(DATABASE_URL, not DATABASE_PATH.exists()))
    manager = falcon_sqla.Manager(engine)
    app = create_app(manager)

    if '--skip-server' not in sys.argv:
        import uvicorn

        uvicorn.run(app, host='127.0.0.1', port=8000)
