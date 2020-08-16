Falcon Middleware: SQLAlchemy Integration
=========================================

The ``falcon-sqla`` package provides a middleware component for managing
`SQLAlchemy sessions <https://docs.sqlalchemy.org/orm/session_api.html#Session>`_.
The manager component can also serve as a base building block or a recipe for
more complex use cases, such as applications leveraging multiple database
binds.


Installation
------------

Simply install the `falcon-sqla <https://pypi.org/project/falcon-sqla/>`__
package from PyPi:

.. code:: bash

    $ pip install falcon-sqla

For more installation options, see :ref:`installation`.


Usage
-----

Configuring the :class:`falcon_sqla.Manager` middleware in a ``falcon.API`` (to
be renamed to ``falcon.App`` in Falcon 3.0+):

.. code:: python

    engine = create_engine('dialect+driver://my/database')
    manager = falcon_sqla.Manager(engine)

    app = falcon.API(middleware=[manager.middleware])

    # The database session will be available as req.context.session

More usage scenarios are covered in the :ref:`user-guide`.


.. toctree::
    :maxdepth: 2
    :caption: Package Documentation

    install
    user
    api/index
