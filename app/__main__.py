"""`python -m app` starts the server.

HTTPS + HTTP/2 if TLS_CERT_FILE and TLS_KEY_FILE are set, otherwise plain HTTP.
"""

import asyncio
import os
import signal
import sys
from collections.abc import Mapping

from hypercorn.asyncio import serve
from hypercorn.config import Config

from app.main import app


def build_config(env: Mapping[str, str]) -> Config:
    cert, key = env.get("TLS_CERT_FILE"), env.get("TLS_KEY_FILE")
    if bool(cert) != bool(key):
        sys.exit("Set both TLS_CERT_FILE and TLS_KEY_FILE, or neither.")
    config = Config()
    port = env.get("PORT", "8443" if cert else "8080")
    # has to be 0.0.0.0 in a container or nothing outside can reach it
    config.bind = [f"0.0.0.0:{port}"]  # noqa: S104
    config.accesslog = "-"
    if cert:
        # setting certfile turns TLS on, and hypercorn offers h2 first in ALPN
        config.certfile, config.keyfile = cert, key
    return config


async def main() -> None:
    config = build_config(os.environ)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    # k8s sends SIGTERM before killing the pod, so let open requests finish first
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await serve(app, config, shutdown_trigger=stop.wait)


if __name__ == "__main__":
    asyncio.run(main())
