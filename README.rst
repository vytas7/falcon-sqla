|Build Status| |codecov.io|

Falcon Middleware: SQLAlchemy Integration
=========================================

The ``falcon-sqla`` package provides a middleware component for managing
`SQLAlchemy sessions <https://docs.sqlalchemy.org/orm/session_api.html#Session>`_.
The manager component can also serve as a base building block or a recipe for
more complex use cases, such as applications leveraging multiple database
binds.


Installation
------------

.. code:: bash

    $ pip install falcon-sqla


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

    engine = create_engine('dialect+driver://my/database')
    manager = falcon_sqla.Manager(engine)

    app = falcon.API(middleware=[manager.middleware])

    # The database session will be available as req.context.session

Context Manager
^^^^^^^^^^^^^^^

A ``falcon_sqla.Manager`` can also explicitly provide a database session using
the ``session_scope()`` context manager:

.. code:: python

    # Somewhere inside a responder
    with self.manager.session_scope(req, resp) as session:
        # Use the session
        # <...>

``session_scope()`` can also be used as a standalone session context outside of
the request-response cycle:

.. code:: python

    with self.manager.session_scope() as session:
        # Use the session
        # <...>

Custom Vertical Partitioning
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Simple random selection of read- and write- database replicas is supported
out of the box. Use the ``add_engine()`` method to instruct the ``Manager`` to
include the provided engines in the runtime bind selection logic:

.. code:: python

    manager = falcon_sqla.Manager(engine)

    read_replica = create_engine('dialect+driver://my/database.replica')
    manager.add_engine(read_replica, 'r')


The ``Manager.get_bind()`` method can be overridden to implement custom engine
selection logic for more complex use cases.

See also this SQLAlchemy recipe:
`Custom Vertical Partitioning
<https://docs.sqlalchemy.org/orm/persistence_techniques.html#custom-vertical-partitioning>`_.


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


.. |Build Status| image:: https://api.travis-ci.org/vytas7/falcon-sqla.svg
   :target: https://travis-ci.org/vytas7/falcon-sqla
.. |codecov.io| image:: https://codecov.io/gh/vytas7/falcon-sqla/branch/master/graphs/badge.svg
   :target: http://codecov.io/gh/vytas7/falcon-sqla
