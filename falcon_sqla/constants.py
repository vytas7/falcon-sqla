#  Copyright 2021 Vytautas Liuolia
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

import enum


class EngineRole(enum.Enum):
    """Engine role in :class:`~falcon_sqla.Manager`."""

    READ = 'r'
    """This engine is only suitable for reading (e.g., a read replica)."""
    WRITE = 'w'
    """
    This engine is only preferred for writing.

    Note:
        A :attr:`~EngineRole.WRITE` engine might still receive read queries
        when, for instance, these are issued from non-idempotent HTTP
        methods. This role should be seen as merely a hint that this engine
        should not be picked when a :attr:`~EngineRole.READ` one is sufficient.
    """
    READ_WRITE = 'rw'
    """
    This engine is suitable for all types of queries.

    When :attr:`choosing<falcon_sqla.Manager.get_bind>`, this
    engine will participate in balancing load in both :attr:`~EngineRole.READ`
    and :attr:`~EngineRole.WRITE` contexts (unless
    :attr:`~.SessionOptions.read_from_rw_engines` is set to ``True``).
    """


class SessionCleanup(enum.Enum):
    """Session cleanup behavior."""

    COMMIT_ON_SUCCESS = 'default'
    COMMIT = 'commit'
    ROLLBACK = 'rollback'
    CLOSE_ONLY = 'close'
