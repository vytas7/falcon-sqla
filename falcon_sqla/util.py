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


class ClosingStreamWrapper:

    def __init__(self, stream, close):
        self._stream = stream
        self._close = close

    def __iter__(self):
        return self._stream

    def close(self):
        try:
            self._close()
        finally:
            close_stream = getattr(self._stream, 'close', None)
            if close_stream:
                close_stream()
