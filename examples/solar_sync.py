#!/usr/bin/env python3
"""Solar System: a small ``falcon-sqla`` example.

A read/write REST API over an SQLite database of celestial bodies in the
Solar System, wired up using the :class:`falcon_sqla.Manager` middleware.

On the first run the SQLite database is created from the declarative base
and populated from ``solar_system.json`` next to this file. Sedna and its
satellite are intentionally absent from the seed data and are added using
the :meth:`~falcon_sqla.Manager.session_scope` API instead, to illustrate
how to use the manager outside of the request-response cycle.

Run directly to launch a local development server::

    $ python solar_sync.py
    Database:  .../example/solar_system.sqlite
    Serving on http://127.0.0.1:8000 (Ctrl+C to stop)

    $ curl http://127.0.0.1:8000/planets
"""

from __future__ import annotations

import json
import pathlib
from typing import Any
from wsgiref.simple_server import make_server

import falcon
from sqlalchemy import create_engine
from sqlalchemy import Engine
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import MappedAsDataclass

import falcon_sqla

HERE = pathlib.Path(__file__).resolve().parent
DATABASE_PATH = HERE / 'solar_system.sqlite'
DATA_PATH = HERE / 'solar_system.json'


class Base(MappedAsDataclass, DeclarativeBase, kw_only=True):
    """Declarative base."""


class CelestialBody(Base):
    __abstract__ = True

    name: Mapped[str] = mapped_column(primary_key=True)

    mass: Mapped[float]
    radius: Mapped[float]
    distance: Mapped[float | None]
    """To be precise, this is the semi-major axis."""

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name.title(),
            'mass': self.mass,
            'radius': self.radius,
            'distance': self.distance,
        }


class Star(CelestialBody):
    __tablename__ = 'stars'


class Planet(CelestialBody):
    __tablename__ = 'planets'


class DwarfPlanet(CelestialBody):
    __tablename__ = 'dwarf_planets'


class Satellite(CelestialBody):
    __tablename__ = 'satellites'

    primary: Mapped[str]

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), 'primary': self.primary.title()}


KINDS: dict[str, type[CelestialBody]] = {
    'stars': Star,
    'planets': Planet,
    'dwarf_planets': DwarfPlanet,
    'satellites': Satellite,
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

    def on_get(
        self, req: falcon.Request, resp: falcon.Response, name: str
    ) -> None:
        body = req.context.session.get(self._model, name.lower())
        if body is None:
            raise falcon.HTTPNotFound()
        resp.media = body.to_dict()

    def on_put(
        self, req: falcon.Request, resp: falcon.Response, name: str
    ) -> None:
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


def _seed(engine: Engine, manager: falcon_sqla.Manager) -> None:
    Base.metadata.create_all(engine)

    with manager.session_scope() as session:
        data = json.loads(DATA_PATH.read_text(encoding='utf-8'))
        for kind, items in data.items():
            for item in items:
                item = {**item, 'name': item['name'].lower()}
                if 'primary' in item:
                    item['primary'] = item['primary'].lower()
                session.add(KINDS[kind](**item))

    # Sedna, Eris and Eris's moon Dysnomia are deliberately left out of
    # solar_system.json to demonstrate how to add records via the manager's
    # session_scope() context manager, e.g. from a one-off script or a CLI
    # subcommand.
    with manager.session_scope() as session:
        session.add(
            DwarfPlanet(
                name='sedna',
                mass=1.0e21,
                radius=500.0,
                distance=7.57e10,
            )
        )
        session.add(
            DwarfPlanet(
                name='eris',
                mass=1.6466e22,
                radius=1163.0,
                distance=1.01237e10,
            )
        )
        session.add(
            Satellite(
                name='dysnomia',
                mass=8.2e19,
                radius=350.0,
                distance=37273.0,
                primary='eris',
            )
        )


fresh = not DATABASE_PATH.exists()
engine = create_engine(f'sqlite:///{DATABASE_PATH}')
manager = falcon_sqla.Manager(engine)

if fresh:
    _seed(engine, manager)

app = falcon.App(middleware=[manager.middleware])
for _kind, _model in KINDS.items():
    _resource = BodyResource(_model)
    app.add_route(f'/{_kind}', _resource, suffix='collection')
    app.add_route(f'/{_kind}/{{name}}', _resource)


if __name__ == '__main__':
    print(f'Database:  {DATABASE_PATH}')
    print('Serving on http://127.0.0.1:8000 (Ctrl+C to stop)')
    with make_server('127.0.0.1', 8000, app) as httpd:
        httpd.serve_forever()
