from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import mcp_server.server as server


class _FakeApp:
    def __init__(self, name: str) -> None:
        self.name = name
        self.list_tools_handler: Any = None
        self.call_tool_handler: Any = None

    def list_tools(self) -> Any:
        def decorator(func: Any) -> Any:
            self.list_tools_handler = func
            return func

        return decorator

    def call_tool(self) -> Any:
        def decorator(func: Any) -> Any:
            self.call_tool_handler = func
            return func

        return decorator

    async def run(self, read_stream: object, write_stream: object, options: object) -> None:
        _ = (read_stream, write_stream, options)

    def create_initialization_options(self) -> object:
        return {"fake": True}


def test_create_app_registers_tools_and_dispatches_calls(monkeypatch: Any) -> None:
    created_apps: list[_FakeApp] = []

    def fake_server_ctor(name: str) -> _FakeApp:
        app = _FakeApp(name)
        created_apps.append(app)
        return app

    def fake_import_module(name: str) -> object:
        if name == "mcp.server":
            return SimpleNamespace(Server=fake_server_ctor)
        if name == "mcp.types":
            return SimpleNamespace(
                Tool=lambda **kwargs: dict(kwargs),
                TextContent=lambda **kwargs: dict(kwargs),
            )
        raise AssertionError(f"unexpected module import: {name}")

    monkeypatch.setattr(server, "import_module", fake_import_module)

    app = server.create_app()

    assert created_apps == [app]
    assert created_apps[0].name == "radar-template"

    tools = asyncio.run(created_apps[0].list_tools_handler())
    tool_names = {tool["name"] for tool in tools}
    assert {"search", "recent_updates", "sql", "top_trends", "price_watch"} <= tool_names

    result = asyncio.run(created_apps[0].call_tool_handler("price_watch", {"threshold": 10.0}))

    assert result == [
        {
            "type": "text",
            "text": "Not available in template project",
        }
    ]
