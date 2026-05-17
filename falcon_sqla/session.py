#  Copyright 2020-2025 Vytautas Liuolia
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from __future__ import annotations

from typing import Any, Callable, Optional, Union

from sqlalchemy import Connection
from sqlalchemy import Engine
import sqlalchemy.orm


class RequestSession(sqlalchemy.orm.Session):
    """
    Custom session that is associated with a Falcon request.

    The Falcon request and response objects are passed inside the session's
    ``info`` context as ``'req'`` and ``'resp'`` keys, respectively.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._manager_get_bind: Optional[
            Callable[..., Union[Engine, Connection]]
        ] = kwargs.pop('_manager_get_bind', None)
        super().__init__(*args, **kwargs)

    def get_bind(
        self,
        mapper: Any = None,
        clause: Any = None,
        **kw: Any,
    ) -> Union[Engine, Connection]:
        """
        Use the manager to get the appropriate bind when ``_manager_get_bind``
        is defined. Otherwise, the default logic is used.

        This method is called by SQLAlchemy.
        """
        if self._manager_get_bind:
            return self._manager_get_bind(
                session=self, mapper=mapper, clause=clause, **self.info
            )
        return super().get_bind(mapper=mapper, clause=clause, **kw)
