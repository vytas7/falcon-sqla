Falcon Middleware: SQLAlchemy Integration
=========================================

The ``falcon-sqla`` package provides a middleware component for managing
`SQLAlchemy sessions <https://docs.sqlalchemy.org/orm/session_api.html#Session>`_.
The manager component can also serve as a base building block or a recipe for
more complex use cases, such as applications leveraging multiple database
binds.


Installation
------------

Until this package is published on `PyPi <https://pypi.org/>`_::

  pip install git+https://github.com/vytas7/falcon-sqla


Usage
-----

The ``falcon_sqla`` session ``Manager`` can be used in two ways:

* As a `Falcon middleware component
  <https://falcon.readthedocs.io/en/stable/api/middleware.html>`_
* As a context manager to explicitly provide a database session


Configuration
^^^^^^^^^^^^^

* Create a SQLAlchemy engine.
* Pass the engine to the ``Manager()`` initializer as its first parameter.
* If using the manager as a middleware component, pass its ``middleware``
  property to the ``falcon.API()`` (to be renamed to ``falcon.App`` in
  Falcon 3.0+) initializer:

.. code:: python

    engine = create_engine('driver+dialect://my/database')
    manager = falcon_sqla.Manager(engine)
    # TODO: document manager.add_engine(...)

    app = falcon.API(middleware=[manager.middleware])

    # The database session will be available as req.context.session

Context Manager
^^^^^^^^^^^^^^^

Asking the ``falcon_sqla.Manager`` to explicitly provide a database session:

.. code:: python

    # Somewhere inside a responder
    with self.manager.session_scope(req, resp) as session:
        # Use the session
        # <...>


About Falcon
------------

`Falcon <https://falconframework.org/>`_ is the minimalist web API framework
for building reliable, correct, and high-performance REST APIs, microservices,
proxies, and app backends in Python.


About SQLAlchemy
----------------

`SQLAlchemy <https://www.sqlalchemy.org/>`_ is the Python SQL toolkit and
Object Relational Mapper that gives application developers the full power and
flexibility of SQL.
