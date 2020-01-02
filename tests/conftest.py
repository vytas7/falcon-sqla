import os
import sqlite3

from sqlalchemy import Column, Integer, String, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

import pytest


@pytest.fixture
def base():
    Base = declarative_base()

    class Language(Base):
        __tablename__ = 'languages'
        __table_args__ = {'sqlite_autoincrement': True}

        id = Column(Integer, primary_key=True)
        name = Column(String(16))
        created = Column(Integer)

    class Engineer(Base):
        __tablename__ = 'engineers'
        __table_args__ = {'sqlite_autoincrement': True}

        id = Column(Integer, primary_key=True)
        name = Column(String, nullable=False)
        languageid = Column(ForeignKey(Language.id))

        language = relationship(Language, backref='engineers')

    return Base


@pytest.fixture
def create_engines(base):
    # NOTE(vytas): Hack until we only support SQLAlchemy with improvement:
    #   https://github.com/sqlalchemy/sqlalchemy/issues/4863
    def connect_ro():
        uri_ro = 'file:' + path + '?mode=ro'
        return sqlite3.connect(uri_ro, uri=True)

    def create():
        uri = 'sqlite:///' + path
        engines = {
            'read': create_engine('sqlite://', creator=connect_ro),
            'write': create_engine(uri),
        }
        base.metadata.create_all(engines['write'])

        return engines

    path = os.environ.get('FALCON_SQLA_TEST_DB', '/tmp/falcon-sqla/test.db')
    if not os.path.exists(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))

    yield create

    try:
        os.unlink(path)
    except OSError:
        pass
