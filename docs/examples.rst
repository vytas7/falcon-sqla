Examples
========

Solar System (WSGI)
-------------------

This example showcases a simple read/write REST API over an SQLite database of
celestial bodies in the solar system, wired up using the
:class:`falcon_sqla.Manager` middleware.

On the first run the SQLite database is created from the declarative base
and populated from ``examples/solar_system.json``.

Stars (only the Sun), planets, dwarf planets, and satellites are stored in SQL
tables defined using SQLAlchemy's ``DeclarativeBase``.
Planets and dwarf planets share a single ``planets`` table at the schema
level (distinguished by a polymorphic discriminator), which lets
``satellites.primary`` be a single foreign key targeting either kind.

.. literalinclude:: ../examples/solar_sync.py
    :language: python
    :caption: examples/solar_sync.py

.. tip::
    You can find this and other examples in ``falcon-sqla``'s GitHub
    repository: https://github.com/vytas7/falcon-sqla/tree/master/examples.

Run directly to launch a local development server on http://localhost:8000::

    $ examples/solar_sync.py

Perform an API request::

    $ curl http://localhost:8000/stars

Each collection is exposed under a URL slug derived from its model class name
lower-cased with a trailing ``s``; ``DwarfPlanet`` is therefore reached at
``/dwarfplanets`` (no underscore), alongside ``/stars``, ``/planets`` and
``/satellites``.

The astute reader will notice that minor dwarf planets and lesser known
satellites are missing from the responses.

Let's run the example interactively, skipping the serving part::

    $ python -i examples/solar_sync.py --skip-server

We can use the manager's :meth:`~falcon_sqla.Manager.session_scope` context
manager to add records; for instance, let's add
`Eris <https://en.wikipedia.org/wiki/Eris_(dwarf_planet)>`__:

>>> with manager.session_scope() as session:
...     session.add(DwarfPlanet(
...         name='eris', mass=1.6466e22, radius=1163.0, distance=1.01237e10))
...

Let's run the server again. The SQLite file lives next to the script and
persists across runs, so Eris is still in the database from the previous
step.

We can also add celestial bodies via the API; we'll
use the popular Python ``requests`` client. Open a separate interpreter in
parallel to the API:

>>> import requests
>>> requests.put(
...     'http://localhost:8000/satellites/dysnomia',
...     json={'mass': 8.2e19, 'radius': 350, 'distance': 37273, 'primary': 'Eris'})
<Response [201]>


Solar System (ASGI)
-------------------

``solar_async.py`` is an asynchronous port of the WSGI example, exposing the
same schema and routes through :class:`falcon.asgi.App` on top of an
``AsyncEngine`` backed by ``aiosqlite``.

.. literalinclude:: ../examples/solar_async.py
    :language: python
    :caption: examples/solar_async.py

Running it requires the asynchronous SQLite driver and an ASGI server such as
``uvicorn``::

    $ pip install aiosqlite uvicorn
    $ examples/solar_async.py

The script writes to ``examples/solar_async.sqlite`` so the two examples can
coexist without stepping on each other's data.

In addition to directly manipulating the database and sending HTTP requests,
another easy way to interact with the application is Falcon's
`TestClient <https://falcon.readthedocs.io/api/testing.html#falcon.testing.TestClient>`__;
it supports both WSGI and ASGI apps.

Let's import this async example interactively::

    $ python -i examples/solar_async.py --skip-server

We can now simulate requests against the ``app``:

>>> client = TestClient(app)
>>> client.get('/stars/sun')
Result<200 OK application/json b'{"name": "Sun", "mas...0, "distance": null}'>
>>> client.put(
...     '/planets/eris',
...     json={'mass': 1.6466e22, 'radius': 1163.0, 'distance': 1.01237e10})
Result<201 Created application/json b'{"name": "Eris", "ma...0, "satellites": []}'>

A handful of notable differences from the synchronous version:

* The engine is constructed with
  ``sqlalchemy.ext.asyncio.create_async_engine``, and the
  ``PRAGMA foreign_keys = ON`` listener is attached to ``engine.sync_engine``
  because SQLAlchemy's event system is synchronous.
* :meth:`~falcon_sqla.Manager.session_scope` is used with ``async with``
  rather than ``with`` (mixing the two raises a :exc:`TypeError` with a
  hint about the right form).
* Asynchronous sessions cannot lazy-load relationships, so each query for a
  ``Planet`` or ``DwarfPlanet`` eager-loads ``satellites`` via
  ``sqlalchemy.orm.selectinload``.
* ``HTTP_799`` from the `7XX Toolkit <https://github.com/joho/7XX-rfc>`__
  is unregistered and not supported under ASGI (servers look up status
  phrases by the numeric code), so refusing a write to ``/stars/{name}``
  yields a registered ``422 Unprocessable Entity`` instead.
