#  Copyright 2021-2023 Vytautas Liuolia
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
    """This engine is only preferred for writing.

    Note:
        A :attr:`~EngineRole.WRITE` engine might still receive read queries
        when, for instance, these are issued from non-idempotent HTTP
        methods. This role should be seen as merely a hint that this engine
        should not be picked when a :attr:`~EngineRole.READ` one is sufficient.
    """

    READ_WRITE = 'rw'
    """This engine is suitable for all types of queries.

    When :attr:`choosing <falcon_sqla.Manager.get_bind>`, this
    engine will participate in balancing load in both :attr:`~EngineRole.READ`
    and :attr:`~EngineRole.WRITE` contexts (unless
    :attr:`~.SessionOptions.read_from_rw_engines` is set to ``True``).
    """


class SessionCleanup(enum.Enum):
    """Session cleanup behavior.

    Sessions are automatically cleaned up and returned to the pool when using
    :class:`~falcon_sqla.Manager`\\'s
    :func:`~falcon_sqla.Manager.session_scope` or
    :attr:`~falcon_sqla.Manager.middleware`.
    In addition to closing the session, to the mode-specific behavior is
    governed by the below constants.

    Unless configured otherwise, the default behavior throughout this add-on is
    :attr:`COMMIT_ON_SUCCESS`.
    """

    COMMIT_ON_SUCCESS = 'default'
    """
    Commit on success (the default behavior).

    This mode attempts to commit in the case there was no exception raised in
    the block in question (or in the case of middleware, request-response
    cycle), otherwise rollback.
    """

    COMMIT = 'commit'
    """Always commit.

    This mode always attempts to commit regardless of any exceptions raised.
    """

    ROLLBACK = 'rollback'
    """Rollback.

    This mode always attempts to rollback regardless of any exceptions raised.
    """

    CLOSE_ONLY = 'close'
    """Close only.

    This mode only closes the session. Any commit or rollback should be
    performed explicitly in the code.
    """
