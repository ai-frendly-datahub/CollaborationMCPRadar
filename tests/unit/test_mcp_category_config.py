from __future__ import annotations

from pathlib import Path

from radar.analyzer import apply_entity_rules
from radar.collector import parse_markdown_section_items
from radar.config_loader import load_category_config, load_category_quality_config
from radar.models import Article, CategoryConfig, Source


def _category_name() -> str:
    configs = sorted(Path("config/categories").glob("*.yaml"))
    assert len(configs) == 1
    return configs[0].stem


def _seed_source(category: CategoryConfig) -> Source:
    seeds = [source for source in category.sources if source.type == "github_readme_section"]
    assert len(seeds) == 1
    return seeds[0]


def _mcp_source(category: CategoryConfig, repository: str) -> Source:
    return next(
        source
        for source in category.sources
        if source.type == "mcp_server" and source.config.get("repository") == repository
    )


def test_mcp_category_config_uses_readme_section_source() -> None:
    category = load_category_config(_category_name())

    source = _seed_source(category)
    assert source.type == "github_readme_section"
    assert (
        source.url
        == "https://raw.githubusercontent.com/darjeeling/awesome-mcp-korea/main/README.md"
    )
    assert source.section
    assert source.trust_tier == "T4_community"
    assert source.collection_tier == "C1_static_list"
    assert source.content_type == "mcp_directory"
    assert {entity.name for entity in category.entities} >= {
        "MCPDomain",
        "Provider",
        "Capability",
        "RiskScope",
        "ProjectHealth",
    }


def test_mcp_category_config_matches_section_entries() -> None:
    category = load_category_config(_category_name())
    seed_source = _seed_source(category)
    section = seed_source.section
    markdown = f"""
### {section}

**[example-mcp](https://github.com/example/example-mcp)** - {section} MCP server with API search tools.

### Other Section

**[other-mcp](https://github.com/example/other-mcp)** - Another MCP server.
"""

    items = parse_markdown_section_items(markdown, section)
    assert len(items) == 1

    article = Article(
        title=items[0]["title"],
        link=items[0]["link"],
        summary=items[0]["summary"],
        source=seed_source.name,
        category=category.category_name,
    )
    analyzed = apply_entity_rules([article], category.entities)

    assert analyzed[0].matched_entities
    assert "MCPDomain" in analyzed[0].matched_entities
    assert "ProjectHealth" in analyzed[0].matched_entities


def test_mcp_server_sources_are_disabled_metadata_candidates() -> None:
    category = load_category_config(_category_name())
    candidates = [source for source in category.sources if source.type == "mcp_server"]
    if category.category_name != "misc_mcp":
        assert candidates

    allowed_statuses = {
        "metadata_only",
        "blocked_command_unresolved",
        "blocked_env_required",
        "blocked_tool_allowlist_unresolved",
        "blocked_runtime_config_unresolved",
        "candidate_ready_for_fake_transport_test",
        "fake_transport_smoke_test_passed",
    }
    for source in candidates:
        metadata_refresh_status = str(source.config.get("metadata_refresh_status") or "")
        assert source.enabled is False
        assert source.collection_tier == "C4_mcp_tool"
        assert source.content_type == "mcp_tool_result"
        assert source.config["activation_status"] in allowed_statuses
        assert source.config["repository"]
        assert isinstance(source.config.get("tools", []), list)
        assert isinstance(source.config.get("resources", []), list)
        assert metadata_refresh_status in {"passed", "not_found"}
        assert source.config["docs_advisory_audit_artifact"]
        if metadata_refresh_status == "not_found":
            assert source.config["docs_advisory_audit_status"] == "repository_not_found"
            assert source.config["github_readme_present"] is False
            assert source.config["github_docs_present"] is False
            assert source.config["github_docs_paths"] == []
        else:
            assert source.config["docs_advisory_audit_status"] == "passed"
            assert source.config["github_readme_present"] is True
            assert source.config["github_docs_present"] is True
            assert source.config["github_docs_paths"]
        assert source.config["github_security_advisory_access_status"].startswith("checked")
        assert source.config["github_security_advisory_count"] >= 0
        if source.config.get("command_discovery_status"):
            assert source.config["command_discovery_checked_at"]
            assert (
                source.config["command_discovery_artifact"]
                == "_workspace/2026-04-30_cycle71_mcp_command_discovery_audit.json"
            )
        if "command_or_endpoint_unresolved" in source.config.get("activation_gates", []):
            assert source.config["command_discovery_status"]
        if source.config["activation_status"] != "metadata_only":
            assert source.config["activation_audited_at"]
            assert source.config["activation_gates"]


def test_mcp_category_config_covers_current_directory_seed_repositories() -> None:
    category = load_category_config(_category_name())
    candidate_repositories = {
        str(source.config.get("repository"))
        for source in category.sources
        if source.type == "mcp_server"
    }

    assert candidate_repositories >= {
        "dooray-go/dooray_mcp",
        "kwanok/dooray-mcp",
        "mskim8717/dooray-mcp",
        "hyeri0903/naver-works-mcp",
    }


def test_mcp_category_quality_config_tracks_mcp_event_models() -> None:
    quality_config = load_category_quality_config(_category_name())
    data_quality = quality_config["data_quality"]
    assert isinstance(data_quality, dict)
    outputs = data_quality["quality_outputs"]
    assert isinstance(outputs, dict)
    assert outputs["tracked_event_models"] == [
        "mcp_directory_entry",
        "mcp_tool_result",
        "linked_repository_metadata",
        "risk_scope_signal",
    ]


def test_dooray_candidate_has_tool_allowlist_and_write_risk_gate() -> None:
    category = load_category_config(_category_name())
    source = _mcp_source(category, "kwanok/dooray-mcp")

    assert source.enabled is False
    assert source.config["activation_status"] == "blocked_env_required"
    assert source.config["env"] == ["DOORAY_API_KEY"]
    assert source.config["event_model"] == "mcp_tool_result"
    assert "tool_resource_allowlist_required" not in source.config["activation_gates"]
    assert "tool_allowlist_unresolved" not in source.config["risk_scope"]
    assert "write_or_mutation_possible" in source.config["risk_scope"]
    assert "user_account_scope" in source.config["risk_scope"]
    assert len(source.config["tools"]) == 35
    assert "dooray_list_tasks" in source.config["tools"]
    assert "dooray_send_channel_message" in source.config["tools"]


def test_dooray_go_candidate_command_and_tools_are_resolved() -> None:
    category = load_category_config(_category_name())
    source = _mcp_source(category, "dooray-go/dooray_mcp")

    assert source.enabled is False
    assert source.config["activation_status"] == "blocked_env_required"
    assert source.config["command_discovery_status"] == "resolved_direct_binary"
    assert source.config["command"] == "dooray-mcp"
    assert source.config["args"] == ["--token", "<DOORAY_PERSONAL_TOKEN>"]
    assert source.config["env"] == ["DOORAY_PERSONAL_TOKEN"]
    assert source.config["event_model"] == "mcp_tool_result"
    assert "command_or_endpoint_unresolved" not in source.config["activation_gates"]
    assert "tool_resource_allowlist_required" not in source.config["activation_gates"]
    assert "tool_allowlist_unresolved" not in source.config["risk_scope"]
    assert "write_or_mutation_possible" in source.config["risk_scope"]
    assert source.config["tools"] == [
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


def test_dooray_go_candidate_has_fake_transport_evidence() -> None:
    category = load_category_config(_category_name())
    source = _mcp_source(category, "dooray-go/dooray_mcp")

    assert source.config["fake_transport_smoke_test_status"] == "passed"
    assert (
        source.config["fake_transport_smoke_test_artifact"]
        == "_workspace/2026-05-02_cycle85_collaboration_dooray_go_fake_probe.json"
    )
    assert source.config["fake_transport_fixture"] == "fixtures/mcp/fake_dooray_go_dooray_mcp.py"
    assert "fake_transport_smoke_test_required" not in source.config["activation_gates"]
    assert "real_transport_smoke_test_required" in source.config["activation_gates"]


def test_kwanok_dooray_candidate_has_fake_transport_evidence() -> None:
    category = load_category_config(_category_name())
    source = _mcp_source(category, "kwanok/dooray-mcp")

    assert source.config["fake_transport_smoke_test_status"] == "passed"
    assert (
        source.config["fake_transport_smoke_test_artifact"]
        == "_workspace/2026-05-02_cycle85_collaboration_kwanok_dooray_fake_probe.json"
    )
    assert source.config["fake_transport_fixture"] == "fixtures/mcp/fake_kwanok_dooray_mcp.py"
    assert "fake_transport_smoke_test_required" not in source.config["activation_gates"]
    assert "real_transport_smoke_test_required" in source.config["activation_gates"]
