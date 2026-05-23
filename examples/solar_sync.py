#!/usr/bin/env python3

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any
import wsgiref.simple_server

import falcon
from falcon import Request
from falcon import Response
from sqlalchemy import create_engine
from sqlalchemy import Engine
from sqlalchemy import event
from sqlalchemy import ForeignKey
from sqlalchemy import select
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import MappedAsDataclass
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Session
from sqlalchemy.pool import ConnectionPoolEntry

import falcon_sqla

HERE = pathlib.Path(__file__).resolve().parent
DATA_PATH = HERE / 'solar_system.json'
DATABASE_PATH = HERE / 'solar_system.sqlite'
DATABASE_URL = f'sqlite:///{DATABASE_PATH}'


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

    def on_get_collection(
        self, req: falcon.Request, resp: falcon.Response
    ) -> None:
        stmt = select(self._model).order_by(self._model.distance)
        resp.media = [
            body.to_dict()
            for body in req.context.session.execute(stmt).scalars()
        ]

    def on_get(self, req: Request, resp: Response, name: str) -> None:
        body = req.context.session.get(self._model, name.lower())
        if body is None:
            raise falcon.HTTPNotFound()
        resp.media = body.to_dict()

    def on_put(self, req: Request, resp: Response, name: str) -> None:
        if self._model is Star:
            raise falcon.HTTPError(
                falcon.HTTP_799,
                description='You cannot change the Sun, or add stars!',
            )

        name = name.lower()
        media = req.get_media()
        media.pop('name', None)
        if 'primary' in media:
            media['primary'] = media['primary'].lower()

        session = req.context.session
        body = session.get(self._model, name)
        if body is None:
            body = self._model(name=name, **media)
            session.add(body)
            resp.status = falcon.HTTP_CREATED
        else:
            for key, value in media.items():
                setattr(body, key, value)
            resp.status = falcon.HTTP_OK
        resp.media = body.to_dict()


def init_engine(url: str, fresh: bool = False) -> Engine:
    engine = create_engine(url)

    @event.listens_for(engine, 'connect')
    def _sqlite_enable_foreign_keys(
        dbapi_connection: DBAPIConnection, _: ConnectionPoolEntry
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')
        cursor.close()

    if fresh:
        print(f'Initializing new database: {engine.url}')
        Base.metadata.create_all(engine)

        # Seed with data from solar_system.json
        with Session(engine) as session:
            data = json.loads(DATA_PATH.read_text())
            for kind, items in data.items():
                for item in items:
                    item = {**item, 'name': item['name'].lower()}
                    if 'primary' in item:
                        item['primary'] = item['primary'].lower()
                    session.add(_KINDS[kind](**item))
            session.commit()
    else:
        print(f'Using existing database: {engine.url}')

    return engine


def create_app(manager: falcon_sqla.Manager) -> falcon.App[Request, Response]:
    app = falcon.App(middleware=[manager.middleware])
    for kind, model in _KINDS.items():
        resource = BodyResource(model)
        app.add_route(f'/{kind}', resource, suffix='collection')
        app.add_route(f'/{kind}/{{name}}', resource)

    return app


if __name__ == '__main__':
    engine = init_engine(DATABASE_URL, not DATABASE_PATH.exists())
    manager = falcon_sqla.Manager(engine)
    app = create_app(manager)

    if '--skip-server' not in sys.argv:
        with wsgiref.simple_server.make_server('127.0.0.1', 8000, app) as srv:
            print('Serving on http://127.0.0.1:8000... (Ctrl+C to stop)')
            srv.serve_forever()
