import logging
import os
import sqlite3

try:
    from psycopg2cffi import compat
    compat.register()
except ImportError:
    pass

import falcon
from sqlalchemy import Column, Integer, String, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

import pytest


@pytest.fixture
def create_app():
    if hasattr(falcon, 'App'):
        return falcon.App
    return falcon.API


@pytest.fixture
def database():
    class Database:
        Base = declarative_base()

        class Language(Base):
            __tablename__ = 'languages'

            id = Column(Integer, primary_key=True)
            name = Column(String(16), nullable=False)
            created = Column(Integer)

        class Snippet(Base):
            __tablename__ = 'snippets'

            id = Column(Integer, primary_key=True)
            code = Column(String, nullable=False)
            languageid = Column(ForeignKey('languages.id'))

            language = relationship('Language', backref='snippets')

        def __init__(self, back_end, write_engine, read_engine):
            self.back_end = back_end
            self.write_engine = write_engine
            self.read_engine = read_engine

        def create_all(self):
            self.Base.metadata.create_all(self.write_engine)

        def drop_all(self):
            self.Base.metadata.drop_all(self.write_engine)

    postgres_uri = os.environ.get('FALCON_SQLA_POSTGRESQL_URI')
    if postgres_uri:
        back_end = 'postgresql'
        write_engine = create_engine(postgres_uri, echo=True)
        args = {'options': '-c default_transaction_read_only=on'}
        read_engine = create_engine(
            postgres_uri, echo=True, connect_args=args)
    else:
        sqlite_path = os.environ.get(
            'FALCON_SQLA_TEST_DB', '/tmp/falcon-sqla/test.db')
        if not os.path.exists(os.path.dirname(sqlite_path)):
            os.makedirs(os.path.dirname(sqlite_path))

        # NOTE(vytas): Hack until we only support SQLAlchemy with this
        #   improvement: https://github.com/sqlalchemy/sqlalchemy/issues/4863
        def connect_ro():
            uri_ro = 'file:' + sqlite_path + '?mode=ro'
            return sqlite3.connect(uri_ro, uri=True)

        back_end = 'sqlite'
        uri = 'sqlite:///' + sqlite_path
        write_engine = create_engine(uri, echo=True)
        read_engine = create_engine(
            uri + '?mode=ro', creator=connect_ro, echo=True)

    db = Database(back_end, write_engine, read_engine)
    db.create_all()

    yield db

    db.drop_all()

    if back_end == 'sqlite':
        try:
            os.unlink(sqlite_path)
        except OSError:
            logging.exception(f'could not unlink {sqlite_path}')
