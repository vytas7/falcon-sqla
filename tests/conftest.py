from sqlalchemy import Column, Integer, String, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

import pytest


@pytest.fixture
def base():
    Base = declarative_base()

    class Language(Base):
        __tablename__ = 'languages'

        id = Column(Integer, primary_key=True)
        name = Column(String(16))

    class Engineer(Base):
        __tablename__ = 'engineers'
        id = Column(Integer, primary_key=True)
        name = Column(String, nullable=False)
        languageid = Column(ForeignKey(Language.id))

        language = relationship(Language, backref='engineers')

    return Base


@pytest.fixture
def engine(base):
    def create(read_only=False):
        db_engine = create_engine('sqlite://')
        if not read_only:
            base.metadata.create_all(db_engine)

        return db_engine

    return create
