# pylint: disable=missing-docstring
# pylint: enable=missing-docstring
# Copyright 2018 Spotify AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import threading
import uuid
import binascii
import struct

import zmq

LOGGER = logging.getLogger(__name__)

class Base(object):
    """
    Base class for running a ZeroMQ event loop in a background thread with a PAIR channel for
    cancelling the background thread.

    Parameters
    ----------
    start : bool
        Whether to start the event loop as a background thread.
    """
    def __init__(self, start):
        self._thread = None
        self._cancel_address = 'inproc://{}'.format(uuid.uuid4().hex)
        self._cancel_parent = zmq.Context.instance().socket(zmq.PAIR)  # pylint: disable=E1101
        self._cancel_parent.bind(self._cancel_address)

        if start:
            self.run_async()

    STATUS = {
        'ok': b'\x00',
        'end': b'\x01',
        'error': b'\x02',
        'timeout': b'\x03',
        'serialization_error': b'\x04',
    }
    STATUS.update({value: key for key, value in STATUS.items()})

    def __enter__(self):
        self.run_async()
        return self

    def __exit__(self, *_):
        self.cancel()

    @property
    def is_alive(self):
        """
        bool : Whether the background thread is alive.
        """
        return self._thread and self._thread.is_alive()

    def cancel(self, timeout=None):
        """
        Cancel the event loop running in a background thread.

        Parameters
        ----------
        timeout : float
            Timeout for joining the background thread.

        Returns
        -------
        cancelled : bool
            Whether the background thread was cancelled. `False` if the background thread was not
            running.
        """
        if self.is_alive:
            self._cancel_parent.send_multipart([b''])
            self._thread.join(timeout)
            self._cancel_parent.close()
            return True
        return False

    def run_async(self):
        """
        Run the event loop in a background thread.
        """
        if not self.is_alive:
            self._thread = threading.Thread(target=self.run)
            self._thread.daemon = True
            self._thread.start()
        return self._thread

    def run(self):
        """
        Run the event loop.

        Notes
        -----
        This call is blocking.
        """
        raise NotImplementedError


def str_to_hex(str):
    return binascii.b2a_hex(str)


def int_to_bytes(int, length):
    bytes = struct.pack('<Q', int)
    assert length <= len(bytes)
    return bytes[:length]


def int_from_bytes(bytes):
    assert len(bytes) <= 8
    bytes = (bytes + b'\x00' * 8)[:8]
    return struct.unpack('<Q', bytes)[0]
