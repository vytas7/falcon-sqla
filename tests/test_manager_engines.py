import pytest
from sqlalchemy import create_engine

from falcon_sqla import EngineRole
from falcon_sqla import Manager


def test_unsupported_role():
    manager = Manager(create_engine('sqlite://'))

    with pytest.raises(ValueError):
        manager.add_engine(create_engine('sqlite://'), 'a+')

    with pytest.raises(ValueError):
        manager.add_engine(create_engine('sqlite://'), 'rb')


def test_use_rw_engines():
    primary, one, two, three = [create_engine('sqlite://') for _ in range(4)]

    manager = Manager(primary)
    assert manager.read_engines == (primary,)
    assert manager.write_engines == (primary,)

    manager.add_engine(one, EngineRole.READ)
    assert manager.read_engines == (primary, one)
    assert manager.write_engines == (primary,)

    manager.add_engine(two, EngineRole.READ_WRITE)
    assert manager.read_engines == (primary, one, two)
    assert manager.write_engines == (primary, two)

    manager.add_engine(three, EngineRole.WRITE)
    assert manager.read_engines == (primary, one, two)
    assert manager.write_engines == (primary, two, three)


def test_prefer_specific_engines():
    primary, one, two, three = [create_engine('sqlite://') for _ in range(4)]

    manager = Manager(primary)
    manager.session_options.read_from_rw_engines = False
    manager.session_options.write_to_rw_engines = False
    assert manager.read_engines == (primary,)
    assert manager.write_engines == (primary,)

    manager.add_engine(one, 'r')
    assert manager.read_engines == (one,)
    assert manager.write_engines == (primary,)

    manager.add_engine(two, 'rw')
    assert manager.read_engines == (one,)
    assert manager.write_engines == (primary, two)

    manager.add_engine(three, 'w')
    assert manager.read_engines == (one,)
    assert manager.write_engines == (three,)
