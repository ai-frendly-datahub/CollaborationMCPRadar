#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from typing import Any

_TOOL_NAMES = [
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


TOOLS = [
    {
        "name": tool_name,
        "title": f"kwanok dooray-mcp {tool_name}",
        "description": f"Return deterministic kwanok dooray-mcp {tool_name} fixture results.",
        "inputSchema": {"type": "object", "additionalProperties": True},
    }
    for tool_name in _TOOL_NAMES
]


def _make_result(tool: str) -> dict[str, Any]:
    slug = tool.replace("_", "-")
    return {
        "title": f"kwanok dooray-mcp {slug} fixture",
        "url": f"https://example.test/collaboration/kwanok-dooray/{slug}-fixture",
        "summary": f"Fixture-only kwanok dooray-mcp {slug} result for collector normalization.",
        "record_id": f"fixture-kwanok-dooray-{slug}",
        "source": "fixture",
    }


RESULTS: dict[str, dict[str, Any]] = {tool: _make_result(tool) for tool in _TOOL_NAMES}


def write_message(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def response_for(message: dict[str, Any]) -> dict[str, Any] | None:
    request_id = message.get("id")
    method = message.get("method")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "fake-kwanok-dooray-mcp",
                    "version": "0.0.0",
                },
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        raw_params = message.get("params")
        params = raw_params if isinstance(raw_params, dict) else {}
        tool_name = str(params.get("name") or "")
        result = RESULTS.get(tool_name)
        if result is None:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": f"Unsupported tool: {tool_name}"}],
                },
            }
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "structuredContent": result,
            },
        }
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Unsupported method: {method}"},
    }


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(message, dict):
            continue
        response = response_for(message)
        if response is not None:
            write_message(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
