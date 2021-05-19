#  Copyright 2020 Vytautas Liuolia
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


import asyncio


class ClosingStreamWrapper:
    """Iterator that wraps a WSGI/ASGI response iterable with support for close().

    This class is used to wrap WSGI/ASGI response streams to provide a side effect
    when the stream is closed.

    If the provided response stream is file-like, i.e., it has a ``read``
    attribute, that attribute is copied to the wrapped instance too.

    Args:
        stream (object): Readable file-like stream object.
        close (callable): A callable object that is called before the stream
            is closed.
    """

    def __init__(self, stream, close):
        self._stream = stream
        self._close = close

        read = getattr(stream, 'read', None)
        if read:
            self.read = read
        self._close_stream = getattr(self._stream, 'close', None)
        if asyncio.iscoroutinefunction(self._close_stream):
            self.close = self.close_async
        elif self._close_stream:
            self.close = self.close_sync
        else:
            self.close = self._close

    def __iter__(self):
        return self._stream

    __aiter__ = __iter__

    def close_sync(self):
        try:
            self._close()
        finally:
            self._close_stream()

    async def close_async(self):
        try:
            self._close()
        finally:
            await self._close_stream()
