from __future__ import annotations

import sys

import pytest

from radar.collector import _collect_single, collect_sources
from radar.exceptions import NetworkError, SourceError
from radar.mcp_source import MCPSourceConfig, collect_mcp_server_source
from radar.models import Source

HANGING_MCP_SERVER = "import time; time.sleep(30)"


def test_mcp_server_source_invokes_allowlisted_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    source = Source(
        name="Example MCP",
        type="mcp_server",
        url="mcp://example",
        config={
            "transport": "stdio",
            "command": "example-mcp",
            "tools": [{"name": "search", "arguments": {"query": "radar"}}],
            "timeout_seconds": 3,
            "max_items": 5,
        },
    )
    observed: dict[str, object] = {}

    def fake_payloads(_source: Source, config: MCPSourceConfig) -> list[object]:
        observed["transport"] = config.transport
        observed["tool"] = config.tools[0].name
        observed["arguments"] = config.tools[0].arguments
        return [
            {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            '{"title": "Example MCP result", '
                            '"url": "https://example.com/result", '
                            '"summary": "normalized from MCP tool"}'
                        ),
                    }
                ]
            }
        ]

    monkeypatch.setattr("radar.mcp_source.collect_mcp_payloads", fake_payloads)

    articles = _collect_single(source, category="mcp", limit=5, timeout=10)

    assert observed == {
        "transport": "stdio",
        "tool": "search",
        "arguments": {"query": "radar"},
    }
    assert len(articles) == 1
    assert articles[0].title == "Example MCP result"
    assert articles[0].link == "https://example.com/result"
    assert articles[0].summary == "normalized from MCP tool"
    assert articles[0].source == "Example MCP"
    assert articles[0].category == "mcp"


def test_disabled_mcp_server_source_is_not_executed(monkeypatch: pytest.MonkeyPatch) -> None:
    source = Source(
        name="Disabled MCP",
        type="mcp_server",
        url="mcp://disabled",
        enabled=False,
        config={"transport": "stdio", "command": "should-not-run", "tools": ["search"]},
    )

    def fail_if_called(_source: Source, _config: MCPSourceConfig) -> list[object]:
        raise AssertionError("disabled MCP source should not be invoked")

    monkeypatch.setattr("radar.mcp_source.collect_mcp_payloads", fail_if_called)

    articles, errors = collect_sources(
        [source],
        category="mcp",
        min_interval_per_host=0.0,
        max_workers=1,
    )

    assert articles == []
    assert errors == []


def test_required_env_missing_fails_before_process_launch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MCP_RADAR_TEST_API_KEY", raising=False)
    source = Source(
        name="Env-gated MCP",
        type="mcp_server",
        url="mcp://env-gated",
        config={
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-c", "raise SystemExit(99)"],
            "tools": ["search"],
            "env": ["MCP_RADAR_TEST_API_KEY"],
            "timeout_seconds": 1,
        },
    )

    with pytest.raises(SourceError, match="Missing required MCP env var"):
        collect_mcp_server_source(source, category="mcp", limit=5, timeout=1)


def test_mcp_payload_without_url_uses_safe_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    source = Source(
        name="Fallback MCP",
        type="mcp_stdio",
        url="",
        id="fallback-mcp",
        config={"command": "example-mcp", "tools": ["list_items"], "max_items": 1},
    )

    def fake_payloads(_source: Source, _config: MCPSourceConfig) -> list[object]:
        return [{"content": [{"type": "text", "text": "plain text result"}]}]

    monkeypatch.setattr("radar.mcp_source.collect_mcp_payloads", fake_payloads)

    articles = _collect_single(source, category="mcp", limit=5, timeout=10)

    assert len(articles) == 1
    assert articles[0].title == "plain text result"
    assert articles[0].link == "mcp://fallback-mcp"


def test_stdio_runtime_timeout_reports_request_context() -> None:
    source = Source(
        name="Hanging MCP",
        type="mcp_server",
        url="mcp://hanging",
        config={
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-c", HANGING_MCP_SERVER],
            "tools": ["search"],
            "timeout_seconds": 1,
        },
    )

    with pytest.raises(NetworkError, match="response 1 after 1s"):
        collect_mcp_server_source(source, category="mcp", limit=5, timeout=1)


def test_dooray_go_fake_stdio_fixture_collects_tool_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOORAY_PERSONAL_TOKEN", "fixture-only")
    tools = [
        "dooray_messenger",
        "dooray_calendar_calendars",
        "dooray_calendar_events",
        "dooray_calendar_post_event",
        "dooray_account_members",
        "dooray_account_member",
        "dooray_project",
        "dooray_posts",
        "os",
    ]
    source = Source(
        name="dooray-go/dooray_mcp",
        type="mcp_server",
        url="https://github.com/dooray-go/dooray_mcp",
        config={
            "transport": "stdio",
            "command": sys.executable,
            "args": ["fixtures/mcp/fake_dooray_go_dooray_mcp.py"],
            "tools": tools,
            "env": ["DOORAY_PERSONAL_TOKEN"],
            "timeout_seconds": 5,
            "max_items": 20,
        },
    )

    articles = collect_mcp_server_source(source, category="collaboration_mcp", limit=20, timeout=5)

    assert len(articles) == len(tools)
    for article in articles:
        assert article.category == "collaboration_mcp"
        assert article.link.startswith("https://example.test/collaboration/dooray-go/")


def test_kwanok_dooray_fake_stdio_fixture_collects_tool_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOORAY_API_KEY", "fixture-only")
    tools = [
        "dooray_add_comment",
        "dooray_add_project_member",
        "dooray_create_channel",
        "dooray_create_milestone",
        "dooray_create_tag",
        "dooray_create_task",
        "dooray_create_template",
        "dooray_delete_comment",
        "dooray_delete_milestone",
        "dooray_delete_template",
        "dooray_get_milestone",
        "dooray_get_project",
        "dooray_get_project_member",
        "dooray_get_tag",
        "dooray_get_task",
        "dooray_get_template",
        "dooray_join_channel_members",
        "dooray_leave_channel_members",
        "dooray_list_channels",
        "dooray_list_comments",
        "dooray_list_milestones",
        "dooray_list_project_members",
        "dooray_list_tags",
        "dooray_list_tasks",
        "dooray_list_templates",
        "dooray_list_workflows",
        "dooray_search_members",
        "dooray_send_channel_message",
        "dooray_send_direct_message",
        "dooray_set_task_done",
        "dooray_set_task_workflow",
        "dooray_update_comment",
        "dooray_update_milestone",
        "dooray_update_task",
        "dooray_update_template",
    ]
    source = Source(
        name="kwanok/dooray-mcp",
        type="mcp_server",
        url="https://github.com/kwanok/dooray-mcp",
        config={
            "transport": "stdio",
            "command": sys.executable,
            "args": ["fixtures/mcp/fake_kwanok_dooray_mcp.py"],
            "tools": tools,
            "env": ["DOORAY_API_KEY"],
            "timeout_seconds": 10,
            "max_items": 50,
        },
    )

    articles = collect_mcp_server_source(source, category="collaboration_mcp", limit=50, timeout=10)

    assert len(articles) == len(tools)
    for article in articles:
        assert article.category == "collaboration_mcp"
        assert article.link.startswith("https://example.test/collaboration/kwanok-dooray/")
