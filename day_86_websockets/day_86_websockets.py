#!/usr/bin/env python3
"""
WebSocket Lifecycle and Real-Time Communication Server

Features:
- HTTP Upgrade handshake using RFC 6455
- Persistent TCP connections
- WebSocket frame encoding and decoding
- Client masking validation
- Text, binary, ping, pong, and close frames
- Connection lifecycle management
- Heartbeat monitoring
- Message-size limits
- Graceful shutdown
- Broadcast messaging
- Connection registry and metrics

Run:
    python websocket_server.py

Connect:
    ws://127.0.0.1:8765
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import secrets
import struct
import time

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


HOST = "127.0.0.1"
PORT = 8765
MAX_MESSAGE_SIZE = 1024 * 1024
HEARTBEAT_INTERVAL = 20
CONNECTION_TIMEOUT = 60
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger("websocket")


class ConnectionState(Enum):
    CONNECTING = "connecting"
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"


class Opcode(Enum):
    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE = 0x8
    PING = 0x9
    PONG = 0xA


@dataclass
class Metrics:
    accepted: int = 0
    active: int = 0
    messages_received: int = 0
    messages_sent: int = 0
    bytes_received: int = 0
    bytes_sent: int = 0
    errors: int = 0


@dataclass
class ClientConnection:
    connection_id: str
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    state: ConnectionState = ConnectionState.CONNECTING
    connected_at: float = field(default_factory=time.monotonic)
    last_activity: float = field(default_factory=time.monotonic)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    fragments: list[bytes] = field(default_factory=list)
    fragment_opcode: Optional[int] = None

    @property
    def remote_address(self) -> str:
        return str(self.writer.get_extra_info("peername"))


class WebSocketError(Exception):
    pass


class WebSocketServer:

    def __init__(self):
        self.connections: dict[str, ClientConnection] = {}
        self.metrics = Metrics()
        self.server: Optional[asyncio.Server] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.shutting_down = False

    @staticmethod
    def accept_key(client_key: str) -> str:
        digest = hashlib.sha1(
            (client_key + GUID).encode("ascii")
        ).digest()

        return base64.b64encode(digest).decode("ascii")

    async def handshake(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> bool:

        try:
            raw = await asyncio.wait_for(
                reader.readuntil(b"\r\n\r\n"),
                timeout=10
            )

            if len(raw) > 16384:
                raise WebSocketError("HTTP headers too large")

            lines = raw.decode("iso-8859-1").split("\r\n")

            request = lines[0].split()

            if len(request) != 3:
                raise WebSocketError("Invalid HTTP request")

            method, path, version = request

            if method != "GET" or version != "HTTP/1.1":
                raise WebSocketError("Invalid upgrade request")

            headers = {}

            for line in lines[1:]:
                if not line:
                    continue

                if ":" not in line:
                    raise WebSocketError("Malformed HTTP header")

                name, value = line.split(":", 1)
                name = name.strip().lower()

                if name in headers:
                    headers[name] += "," + value.strip()
                else:
                    headers[name] = value.strip()

            if "websocket" not in headers.get(
                "upgrade", ""
            ).lower():
                raise WebSocketError("Missing WebSocket upgrade")

            connection_tokens = {
                token.strip().lower()
                for token in headers.get("connection", "").split(",")
            }

            if "upgrade" not in connection_tokens:
                raise WebSocketError("Missing Connection upgrade token")

            if headers.get("sec-websocket-version") != "13":
                raise WebSocketError("Unsupported WebSocket version")

            key = headers.get("sec-websocket-key", "")

            try:
                decoded_key = base64.b64decode(
                    key,
                    validate=True
                )
            except Exception as exc:
                raise WebSocketError("Invalid WebSocket key") from exc

            if len(decoded_key) != 16:
                raise WebSocketError("Invalid WebSocket key length")

            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {self.accept_key(key)}\r\n"
                "\r\n"
            )

            writer.write(response.encode("ascii"))
            await writer.drain()

            logger.info("Handshake completed for %s", path)

            return True

        except (
            asyncio.TimeoutError,
            asyncio.IncompleteReadError,
            UnicodeDecodeError,
            WebSocketError
        ) as exc:

            logger.warning("Handshake rejected: %s", exc)

            try:
                writer.write(
                    b"HTTP/1.1 400 Bad Request\r\n"
                    b"Connection: close\r\n"
                    b"Content-Length: 0\r\n\r\n"
                )
                await writer.drain()
            except (ConnectionError, OSError):
                pass

            return False

    async def read_frame(
        self,
        connection: ClientConnection
    ) -> tuple[bool, int, bytes]:

        reader = connection.reader

        header = await reader.readexactly(2)

        first, second = header

        fin = bool(first & 0x80)
        rsv = first & 0x70
        opcode = first & 0x0F
        masked = bool(second & 0x80)

        if rsv:
            raise WebSocketError("Reserved bits must be zero")

        if not masked:
            raise WebSocketError("Client frames must be masked")

        if opcode not in {0, 1, 2, 8, 9, 10}:
            raise WebSocketError("Invalid opcode")

        length = second & 0x7F

        if length == 126:
            length = struct.unpack(
                "!H",
                await reader.readexactly(2)
            )[0]

            if length < 126:
                raise WebSocketError("Non-minimal frame length")

        elif length == 127:
            extended = await reader.readexactly(8)

            if extended[0] & 0x80:
                raise WebSocketError("Invalid frame length")

            length = struct.unpack("!Q", extended)[0]

            if length < 65536:
                raise WebSocketError("Non-minimal frame length")

        control_frame = opcode >= 8

        if control_frame and (
            not fin or length > 125
        ):
            raise WebSocketError("Invalid control frame")

        if length > MAX_MESSAGE_SIZE:
            raise WebSocketError("Frame exceeds maximum size")

        mask = await reader.readexactly(4)
        payload = bytearray(
            await reader.readexactly(length)
        )

        for index in range(length):
            payload[index] ^= mask[index % 4]

        connection.last_activity = time.monotonic()

        self.metrics.bytes_received += length

        return fin, opcode, bytes(payload)

    @staticmethod
    def encode_frame(
        opcode: int,
        payload: bytes,
        fin: bool = True
    ) -> bytes:

        if opcode >= 8 and (
            not fin or len(payload) > 125
        ):
            raise WebSocketError("Invalid control frame")

        if len(payload) > MAX_MESSAGE_SIZE:
            raise WebSocketError("Outgoing message too large")

        first = (0x80 if fin else 0) | opcode
        length = len(payload)

        if length < 126:
            header = bytes([first, length])

        elif length <= 65535:
            header = bytes([first, 126]) + struct.pack("!H", length)

        else:
            header = bytes([first, 127]) + struct.pack("!Q", length)

        return header + payload

    async def send_frame(
        self,
        connection: ClientConnection,
        opcode: int,
        payload: bytes
    ) -> None:

        if connection.state not in {
            ConnectionState.OPEN,
            ConnectionState.CLOSING
        }:
            return

        frame = self.encode_frame(opcode, payload)

        async with connection.send_lock:

            if connection.writer.is_closing():
                return

            connection.writer.write(frame)
            await asyncio.wait_for(
                connection.writer.drain(),
                timeout=10
            )

        self.metrics.bytes_sent += len(payload)

    async def send_text(
        self,
        connection: ClientConnection,
        message: str
    ) -> None:

        payload = message.encode("utf-8")

        await self.send_frame(
            connection,
            Opcode.TEXT.value,
            payload
        )

        self.metrics.messages_sent += 1

    async def broadcast(
        self,
        message: str,
        exclude: Optional[str] = None
    ) -> None:

        targets = [
            connection
            for connection in self.connections.values()
            if connection.connection_id != exclude
            and connection.state == ConnectionState.OPEN
        ]

        results = await asyncio.gather(
            *[
                self.send_text(connection, message)
                for connection in targets
            ],
            return_exceptions=True
        )

        for connection, result in zip(targets, results):
            if isinstance(result, Exception):
                logger.warning(
                    "Broadcast failed for %s: %s",
                    connection.connection_id,
                    result
                )
                await self.close_connection(connection, 1011)

    async def handle_message(
        self,
        connection: ClientConnection,
        payload: bytes
    ) -> None:

        try:
            message = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            await self.send_text(
                connection,
                json.dumps({
                    "type": "error",
                    "message": "Invalid JSON message"
                })
            )
            return

        if not isinstance(message, dict):
            await self.send_text(
                connection,
                json.dumps({
                    "type": "error",
                    "message": "Expected a JSON object"
                })
            )
            return

        event = message.get("type")

        if event == "echo":
            await self.send_text(
                connection,
                json.dumps({
                    "type": "echo",
                    "data": message.get("data")
                })
            )

        elif event == "broadcast":
            content = message.get("data")

            if not isinstance(content, str) or len(content) > 10000:
                await self.send_text(
                    connection,
                    '{"type":"error","message":"Invalid broadcast data"}'
                )
                return

            await self.broadcast(
                json.dumps({
                    "type": "broadcast",
                    "from": connection.connection_id,
                    "data": content
                }),
                exclude=connection.connection_id
            )

        elif event == "metrics":
            await self.send_text(
                connection,
                json.dumps({
                    "type": "metrics",
                    "accepted": self.metrics.accepted,
                    "active": self.metrics.active,
                    "received": self.metrics.messages_received,
                    "sent": self.metrics.messages_sent
                })
            )

        else:
            await self.send_text(
                connection,
                json.dumps({
                    "type": "error",
                    "message": "Unknown event"
                })
            )

    async def process_frame(
        self,
        connection: ClientConnection,
        fin: bool,
        opcode: int,
        payload: bytes
    ) -> bool:

        if opcode == Opcode.PING.value:
            await self.send_frame(
                connection,
                Opcode.PONG.value,
                payload
            )
            return True

        if opcode == Opcode.PONG.value:
            return True

        if opcode == Opcode.CLOSE.value:

            if len(payload) == 1:
                raise WebSocketError("Invalid close payload")

            if len(payload) >= 2:
                code = struct.unpack("!H", payload[:2])[0]

                if (
                    code < 1000
                    or code >= 5000
                    or code in {1004, 1005, 1006, 1015}
                ):
                    raise WebSocketError("Invalid close code")

                payload[2:].decode("utf-8")

            connection.state = ConnectionState.CLOSING

            await self.send_frame(
                connection,
                Opcode.CLOSE.value,
                payload
            )

            return False

        if opcode == Opcode.CONTINUATION.value:

            if connection.fragment_opcode is None:
                raise WebSocketError("Unexpected continuation")

            connection.fragments.append(payload)

        elif opcode in {
            Opcode.TEXT.value,
            Opcode.BINARY.value
        }:

            if connection.fragment_opcode is not None:
                raise WebSocketError("Nested fragmented message")

            if fin:
                return await self.process_complete_message(
                    connection,
                    opcode,
                    payload
                )

            connection.fragment_opcode = opcode
            connection.fragments = [payload]
            return True

        else:
            raise WebSocketError("Unexpected opcode")

        total_size = sum(
            len(fragment)
            for fragment in connection.fragments
        )

        if total_size > MAX_MESSAGE_SIZE:
            raise WebSocketError("Fragmented message too large")

        if fin:
            complete_payload = b"".join(
                connection.fragments
            )

            original_opcode = connection.fragment_opcode

            connection.fragments.clear()
            connection.fragment_opcode = None

            return await self.process_complete_message(
                connection,
                original_opcode,
                complete_payload
            )

        return True

    async def process_complete_message(
        self,
        connection: ClientConnection,
        opcode: int,
        payload: bytes
    ) -> bool:

        self.metrics.messages_received += 1

        if opcode == Opcode.TEXT.value:
            payload.decode("utf-8")
            await self.handle_message(connection, payload)

        elif opcode == Opcode.BINARY.value:
            await self.send_text(
                connection,
                json.dumps({
                    "type": "error",
                    "message": "Binary messages are not supported"
                })
            )

        return True

    async def close_connection(
        self,
        connection: ClientConnection,
        code: int = 1000
    ) -> None:

        if connection.state == ConnectionState.CLOSED:
            return

        connection.state = ConnectionState.CLOSING

        try:
            if not connection.writer.is_closing():
                reason = "Server closing"
                payload = struct.pack("!H", code) + reason.encode()

                await self.send_frame(
                    connection,
                    Opcode.CLOSE.value,
                    payload
                )
        except (
            ConnectionError,
            OSError,
            asyncio.TimeoutError,
            WebSocketError
        ):
            pass

        connection.state = ConnectionState.CLOSED

        self.connections.pop(
            connection.connection_id,
            None
        )

        self.metrics.active = len(self.connections)

        connection.writer.close()

        try:
            await asyncio.wait_for(
                connection.writer.wait_closed(),
                timeout=3
            )
        except (asyncio.TimeoutError, ConnectionError, OSError):
            pass

        logger.info(
            "Connection closed: %s",
            connection.connection_id
        )

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:

        if self.shutting_down:
            writer.close()
            await writer.wait_closed()
            return

        if not await self.handshake(reader, writer):
            writer.close()
            await writer.wait_closed()
            return

        connection = ClientConnection(
            connection_id=secrets.token_hex(8),
            reader=reader,
            writer=writer
        )

        connection.state = ConnectionState.OPEN

        self.connections[connection.connection_id] = connection

        self.metrics.accepted += 1
        self.metrics.active = len(self.connections)

        logger.info(
            "Connected: %s",
            connection.connection_id
        )

        try:
            await self.send_text(
                connection,
                json.dumps({
                    "type": "connected",
                    "connection_id": connection.connection_id
                })
            )

            while connection.state == ConnectionState.OPEN:

                fin, opcode, payload = await asyncio.wait_for(
                    self.read_frame(connection),
                    timeout=CONNECTION_TIMEOUT
                )

                should_continue = await self.process_frame(
                    connection,
                    fin,
                    opcode,
                    payload
                )

                if not should_continue:
                    break

        except asyncio.TimeoutError:
            logger.warning(
                "Connection timed out: %s",
                connection.connection_id
            )
            await self.close_connection(connection, 1001)

        except asyncio.IncompleteReadError:
            logger.info(
                "Peer disconnected: %s",
                connection.connection_id
            )

        except (
            WebSocketError,
            UnicodeDecodeError,
            ConnectionError,
            OSError,
            asyncio.TimeoutError
        ) as exc:

            self.metrics.errors += 1

            logger.warning(
                "Connection error %s: %s",
                connection.connection_id,
                exc
            )

            await self.close_connection(connection, 1002)

        finally:
            await self.close_connection(connection)

    async def heartbeat(self) -> None:

        while not self.shutting_down:

            await asyncio.sleep(HEARTBEAT_INTERVAL)

            now = time.monotonic()

            for connection in list(self.connections.values()):

                if now - connection.last_activity > CONNECTION_TIMEOUT:
                    await self.close_connection(connection, 1001)

    async def start(self) -> None:

        self.server = await asyncio.start_server(
            self.handle_client,
            HOST,
            PORT,
            limit=MAX_MESSAGE_SIZE + 16384
        )

        self.heartbeat_task = asyncio.create_task(
            self.heartbeat()
        )

        logger.info(
            "WebSocket server listening on ws://%s:%s",
            HOST,
            PORT
        )

        async with self.server:
            await self.server.serve_forever()

    async def shutdown(self) -> None:

        self.shutting_down = True

        logger.info("Starting graceful shutdown")

        if self.server:
            self.server.close()
            await self.server.wait_closed()

        if self.heartbeat_task:
            self.heartbeat_task.cancel()

            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass

        await asyncio.gather(
            *[
                self.close_connection(connection, 1001)
                for connection in list(self.connections.values())
            ],
            return_exceptions=True
        )

        logger.info(
            "Final metrics: %s",
            self.metrics
        )


async def main():

    server = WebSocketServer()

    try:
        await server.start()

    except asyncio.CancelledError:
        pass

    finally:
        await server.shutdown()


if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        logger.info("Server interrupted")
