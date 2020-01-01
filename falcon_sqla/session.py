import sqlalchemy.orm


class RequestSession(sqlalchemy.orm.Session):
    """
    Custom session that is associated with a Falcon request.

    Work in progress.
    """
    pass
