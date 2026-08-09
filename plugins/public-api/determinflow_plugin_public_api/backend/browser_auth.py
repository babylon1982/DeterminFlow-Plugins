"""External-browser PKCE login with a short-lived loopback callback."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
import webbrowser
from collections.abc import Callable
from urllib.parse import parse_qs, urlsplit

from .portal import PortalRequestError, PublicApiPortalClient

_CALLBACK_TIMEOUT_SECONDS = 180
_MAX_REQUEST_HEAD_BYTES = 8192


def _open_default_browser(url: str) -> bool:
    return webbrowser.open(url, new=2)


class BrowserAuthorizationFlow:
    """Authorize one Plugin installation through the user's default browser."""

    def __init__(
        self,
        *,
        opener: Callable[[str], bool] | None = None,
        callback_timeout_seconds: float = _CALLBACK_TIMEOUT_SECONDS,
    ) -> None:
        self._opener = opener or _open_default_browser
        self._callback_timeout_seconds = callback_timeout_seconds

    async def authorize(
        self,
        portal: PublicApiPortalClient,
        installation_id: str,
    ) -> dict[str, str]:
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        loop = asyncio.get_running_loop()
        result: asyncio.Future[str] = loop.create_future()

        async def handle_callback(
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
        ) -> None:
            success = False
            try:
                request_head = await asyncio.wait_for(
                    reader.readuntil(b"\r\n\r\n"),
                    timeout=5,
                )
                if len(request_head) > _MAX_REQUEST_HEAD_BYTES:
                    raise ValueError("request too large")
                request_line = request_head.split(b"\r\n", 1)[0].decode("ascii")
                method, target, _version = request_line.split(" ", 2)
                parsed = urlsplit(target)
                query = parse_qs(parsed.query)
                callback_state = query.get("state", [""])[0]
                if method != "GET" or parsed.path != "/callback":
                    raise ValueError("invalid callback path")
                if not secrets.compare_digest(callback_state, state):
                    raise ValueError("invalid callback state")
                error = query.get("error", [""])[0]
                code = query.get("code", [""])[0]
                if error:
                    if not result.done():
                        result.set_exception(
                            PortalRequestError(
                                "authorization_denied",
                                "笔枢登录已取消",
                            )
                        )
                    raise ValueError("authorization denied")
                if not code:
                    raise ValueError("missing authorization code")
                if not result.done():
                    result.set_result(code)
                success = True
            except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, ValueError):
                success = False

            body = self._callback_page(success)
            status_line = "200 OK" if success else "400 Bad Request"
            response = (
                f"HTTP/1.1 {status_line}\r\n"
                "Content-Type: text/html; charset=utf-8\r\n"
                "Cache-Control: no-store\r\n"
                "Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'\r\n"
                "Referrer-Policy: no-referrer\r\n"
                "X-Content-Type-Options: nosniff\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii") + body
            writer.write(response)
            try:
                await writer.drain()
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass

        server = await asyncio.start_server(
            handle_callback,
            "127.0.0.1",
            0,
            limit=_MAX_REQUEST_HEAD_BYTES,
        )
        try:
            socket = next(iter(server.sockets or []), None)
            if socket is None:
                raise PortalRequestError(
                    "callback_unavailable",
                    "无法启动笔枢登录回调",
                )
            port = int(socket.getsockname()[1])
            redirect_uri = f"http://127.0.0.1:{port}/callback"
            authorization_url = portal.authorization_url(
                installation_id=installation_id,
                redirect_uri=redirect_uri,
                code_challenge=challenge,
                state=state,
            )
            opened = await asyncio.to_thread(self._opener, authorization_url)
            if not opened:
                raise PortalRequestError(
                    "browser_unavailable",
                    "无法打开系统浏览器",
                )
            try:
                code = await asyncio.wait_for(
                    result,
                    timeout=self._callback_timeout_seconds,
                )
            except TimeoutError as exc:
                raise PortalRequestError(
                    "authorization_timeout",
                    "笔枢登录已超时，请重试",
                ) from exc
            return await portal.exchange_authorization_code(
                code=code,
                code_verifier=verifier,
                redirect_uri=redirect_uri,
            )
        finally:
            server.close()
            await server.wait_closed()

    @staticmethod
    def _callback_page(success: bool) -> bytes:
        if success:
            title = "登录已完成"
            message = "可以关闭此页面并返回 DeterminFlow。"
        else:
            title = "登录未完成"
            message = "请返回 DeterminFlow 重试。"
        return (
            "<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{title}</title>"
            "<body style=\"margin:0;min-height:100vh;display:grid;place-items:center;"
            "background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif\">"
            "<main style=\"max-width:420px;padding:32px;text-align:center\">"
            f"<h1 style=\"font-size:24px\">{title}</h1>"
            f"<p style=\"color:#94a3b8\">{message}</p>"
            "</main></body></html>"
        ).encode()
