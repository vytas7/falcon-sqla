.. _user-guide:

User Guide
==========

The ``falcon_sqla`` session :class:`~falcon_sqla.Manager` can be used in two
ways:

* As a `Falcon middleware component
  <https://falcon.readthedocs.io/en/stable/api/middleware.html>`_.
* As a context manager to explicitly provide a database session.


Configuration
-------------

* Create a SQLAlchemy engine.
* Pass the engine to the :class:`Manager() <falcon_sqla.Manager>` initializer
  as its first parameter.
* If using the manager as a middleware component, pass its
  :attr:`~falcon_sqla.Manager.middleware` property to a ``falcon.App()``\'s
  middleware list:

.. code:: python

    engine = create_engine('dialect+driver://my/database')
    manager = falcon_sqla.Manager(engine)

    app = falcon.App(middleware=[manager.middleware])

    # The database session will be available as req.context.session


Context Manager
---------------

A :class:`falcon_sqla.Manager` can also explicitly provide a database session
using the :func:`~falcon_sqla.Manager.session_scope` context manager:

.. code:: python

    # Somewhere inside a responder
    with self.manager.session_scope(req, resp) as session:
        # Use the session
        # <...>

:func:`~falcon_sqla.Manager.session_scope` can also be used as a standalone
session context outside of the request-response cycle:

.. code:: python

    with self.manager.session_scope() as session:
        # Use the session
        # <...>


Custom Vertical Partitioning
----------------------------

Simple random selection of read- and write- database replicas is supported
out of the box. Use the :func:`~falcon_sqla.Manager.add_engine` method to
instruct the :class:`~falcon_sqla.Manager` to include the provided engines in
the runtime bind selection logic:

.. code:: python

    manager = falcon_sqla.Manager(engine)

    read_replica = create_engine('dialect+driver://my/database.replica')
    manager.add_engine(read_replica, 'r')

The :func:`Manager.get_bind() <falcon_sqla.Manager.get_bind>` method can be
overridden to implement custom engine selection logic for more complex use
cases.

See also this SQLAlchemy recipe:
`Custom Vertical Partitioning
<https://docs.sqlalchemy.org/orm/persistence_techniques.html#custom-vertical-partitioning>`_.
