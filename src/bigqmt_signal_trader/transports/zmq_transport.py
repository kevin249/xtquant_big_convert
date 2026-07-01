"""ZeroMQ transport for the BigQMT RPC bridge.

Designed for same-host low latency. Topology:

* **Server** binds a ``ROUTER`` socket. Each inbound message arrives as
  ``[identity, payload]``; the server remembers ``identity`` keyed by
  ``request_id`` and replies with ``[identity, payload]`` so ZMQ routes the
  response back to the originating client automatically.
* **Client** connects a ``DEALER`` socket (with a unique random identity), sends
  ``[payload]``, then ``poll``/``recv`` for the response. DEALER gives each
  client an asymmetric async path that pairs naturally with ROUTER.

Wire framing is a single JSON payload per message. The original b64 stock-code
obfuscation (``encode_rpc_request_payload``) is applied too, so payloads stay
opaque even though ZMQ does not need it — keeps the wire uniform with Redis.

Two threads on the server: the ROUTER recv loop, and a per-client is implicit
(ZMQ handles multiplexing). One thread on the client for recv is avoided by
using DEALER + ``poll`` (synchronous request/response fits the RPC model).
"""

import json
import threading
import time
import uuid

from ..adapters.redis_common import decode_text
from ..redis_rpc import (
    decode_rpc_request_payload,
    encode_rpc_request_payload,
)
from .base import RpcTransport, TransportError, TransportTimeout


DEFAULT_BIND_ADDRESS = "ipc:///tmp/bigqmt_rpc_{account_id}.sock"
DEFAULT_CONNECT_ADDRESS_TEMPLATE = "ipc:///tmp/bigqmt_rpc_{account_id}.sock"


def _loads(raw):
    if isinstance(raw, dict):
        return dict(raw)
    text = decode_text(raw)
    text = decode_rpc_request_payload(text)
    return json.loads(text)


class ZmqTransport(RpcTransport):
    """ZMQ ROUTER/DEALER transport.

    The same instance plays both roles depending on method called:
    ``send_request`` acts as a client (DEALER connect), ``start_receiving`` +
    ``send_response`` act as a server (ROUTER bind). A deployment normally uses
    one instance per role (the QMT process is the server; the external client
    is the client).
    """

    name = "zmq"

    def __init__(
        self,
        bind_address=None,
        connect_address=None,
        account_id="",
        print_prefix="[bigqmt_rpc]",
        io_threads=1,
        recv_timeout_seconds=1.0,
        server_hwm=10000,
        client_linger_ms=0,
    ):
        super(ZmqTransport, self).__init__(account_id=account_id, print_prefix=print_prefix)
        # Resolve default ipc endpoints from account_id so distinct accounts
        # don't collide on the same socket file.
        self.bind_address = bind_address or DEFAULT_BIND_ADDRESS.format(account_id=account_id)
        self.connect_address = connect_address
        self.io_threads = int(io_threads)
        self.recv_timeout_seconds = float(recv_timeout_seconds)
        self.server_hwm = int(server_hwm)
        self.client_linger_ms = int(client_linger_ms)

        self._zmq = None  # imported lazily
        self._ctx = None
        # server state
        self._router = None
        self._router_thread = None
        self._pending_identities = {}  # request_id -> client identity bytes
        self._identity_lock = threading.Lock()
        # client state
        self._dealer = None
        self._client_lock = threading.Lock()

    # -- construction helper ----------------------------------------------
    @classmethod
    def from_config(cls, config, account_id="", print_prefix="[bigqmt_rpc]"):
        config = dict(config or {})
        return cls(
            bind_address=config.get("bind_address"),
            connect_address=config.get("connect_address"),
            account_id=config.get("account_id", account_id),
            print_prefix=print_prefix,
            io_threads=int(config.get("io_threads", 1)),
            recv_timeout_seconds=float(config.get("recv_timeout_seconds", 1.0)),
            server_hwm=int(config.get("server_hwm", 10000)),
            client_linger_ms=int(config.get("client_linger_ms", 0)),
        )

    # -- shared zmq context -----------------------------------------------
    def _ensure_zmq(self):
        if self._zmq is None:
            try:
                import zmq  # noqa: F401
            except ImportError as exc:  # pragma: no cover - depends on env
                raise TransportError(
                    "pyzmq is required for the zmq transport: %s" % exc
                )
            self._zmq = zmq
        if self._ctx is None:
            self._ctx = self._zmq.Context.instance(self.io_threads)
        return self._zmq, self._ctx

    # -- server side ------------------------------------------------------
    def start_receiving(self, on_request, background_threads=True):
        super(ZmqTransport, self).start_receiving(on_request)
        zmq, ctx = self._ensure_zmq()
        self._router = ctx.socket(zmq.ROUTER)
        self._router.setsockopt(zmq.RCVHWM, self.server_hwm)
        self._router.setsockopt(zmq.SNDHWM, self.server_hwm)
        self._router.setsockopt(zmq.RCVTIMEO, int(self.recv_timeout_seconds * 1000))
        self._router.bind(self.bind_address)
        if not background_threads:
            print(
                "%s zmq bound=%s background_threads=False"
                % (self.print_prefix, self.bind_address)
            )
            return
        self._router_thread = threading.Thread(
            target=self._router_loop, name="bigqmt-zmq-rpc", daemon=True
        )
        self._router_thread.start()
        print(
            "%s zmq started bound=%s" % (self.print_prefix, self.bind_address)
        )

    def _router_loop(self):
        zmq = self._zmq
        try:
            while self._running:
                try:
                    frames = self._router.recv_multipart()
                except self._zmq.Again:
                    continue
                except Exception as exc:
                    if not self._running:
                        break
                    print("%s zmq recv failed: %s" % (self.print_prefix, exc))
                    time.sleep(0.5)
                    continue
                if len(frames) < 2:
                    continue
                identity, payload = frames[0], frames[-1]
                try:
                    request = _loads(payload)
                except Exception as exc:
                    print("%s zmq decode failed: %s" % (self.print_prefix, exc))
                    continue
                request_id = str(request.get("request_id") or uuid.uuid4().hex)
                with self._identity_lock:
                    self._pending_identities[request_id] = identity
                try:
                    self.deliver(request)
                except Exception as exc:
                    print("%s zmq deliver failed: %s" % (self.print_prefix, exc))
        finally:
            # Close the ROUTER socket on the thread that owns it. On Windows,
            # closing a ZMQ socket from a different thread trips a signaler
            # assertion (abort); closing it here is safe because this thread
            # created and exclusively used it.
            try:
                self._router.close(linger=0)
            except Exception:
                pass
            self._router = None
            # Deliver to the registered callback. The callback (service) is
            # responsible for calling send_response, which routes via identity.
            try:
                self.deliver(request)
            except Exception as exc:
                print("%s zmq deliver failed: %s" % (self.print_prefix, exc))

    def send_response(self, request, response):
        if self._router is None:
            raise TransportError("zmq server socket is not bound")
        request_id = str(
            response.get("request_id") or request.get("request_id") or ""
        )
        with self._identity_lock:
            identity = self._pending_identities.pop(request_id, None)
        if identity is None:
            # No matching peer — drop silently (client may have gone away).
            return
        payload = encode_rpc_request_payload(response)
        try:
            self._router.send_multipart([identity, payload.encode("utf-8")])
        except Exception as exc:
            print("%s zmq send failed: %s" % (self.print_prefix, exc))

    # -- client side ------------------------------------------------------
    def _ensure_dealer(self):
        zmq, ctx = self._ensure_zmq()
        if self._dealer is None:
            address = self.connect_address or DEFAULT_CONNECT_ADDRESS_TEMPLATE.format(
                account_id=self.account_id
            )
            sock = ctx.socket(zmq.DEALER)
            # Unique identity so ROUTER can route replies back to us.
            sock.setsockopt(zmq.IDENTITY, uuid.uuid4().hex.encode("utf-8")[:16])
            sock.setsockopt(zmq.LINGER, self.client_linger_ms)
            sock.connect(address)
            self._dealer = sock
            self.connect_address = address
        return self._dealer

    def send_request(self, request, timeout_seconds, **_kwargs):
        zmq = self._zmq or self._ensure_zmq()[0]
        with self._client_lock:
            dealer = self._ensure_dealer()
            request = dict(request)
            request.setdefault("request_id", uuid.uuid4().hex)
            request_id = request["request_id"]
            payload = encode_rpc_request_payload(request)
            try:
                dealer.send(payload.encode("utf-8"))
            except Exception as exc:
                raise TransportError("zmq send failed: %s" % exc)
            deadline = time.time() + float(timeout_seconds)
            poller = self._zmq.Poller()
            poller.register(dealer, self._zmq.POLLIN)
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                events = dict(poller.poll(timeout=int(remaining * 1000)))
                if dealer in events:
                    frames = dealer.recv_multipart()
                    raw = frames[-1]
                    response = _loads(raw)
                    if response.get("request_id") == request_id:
                        return response
            raise TransportTimeout("zmq rpc timeout: %s" % request.get("method"))

    # -- lifecycle --------------------------------------------------------
    def stop(self):
        super(ZmqTransport, self).stop()
        # Clear _running so the router loop exits; the loop closes its own
        # socket (closing cross-thread trips a Windows signaler abort).
        if self._router_thread is not None and self._router_thread.is_alive():
            self._router_thread.join(2.0)
        self._router_thread = None
        with self._client_lock:
            if self._dealer is not None:
                try:
                    self._dealer.close(linger=self.client_linger_ms)
                except Exception:
                    pass
                self._dealer = None
        # Do NOT terminate the shared context — other sockets/users may rely on it.
