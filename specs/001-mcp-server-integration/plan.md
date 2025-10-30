# Implementation Plan: MCP Server Integration

**Branch**: `001-mcp-server-integration` | **Date**: 2025-10-31 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-mcp-server-integration/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Integrate FASTMCP server as exclusive automation backend for AI agent-driven Android app crawling. All device actions routed through MCP protocol, removing direct Appium logic from crawler.

## Technical Context

**Language/Version**: Python 3.8+  
**Primary Dependencies**: FASTMCP, Appium 2.0+, AI providers (Gemini/Ollama/OpenRouter), pytest  
**Storage**: SQLite database for sessions and logs, file system for screenshots/XML  
**Testing**: pytest with contract and integration tests  
**Target Platform**: Windows/Linux development, Android runtime  
**Project Type**: CLI Python application  
**Performance Goals**: 10-50 actions per minute, <5s average action latency  
**Constraints**: 100% MCP protocol compliance, no direct Appium calls in crawler  
**Scale/Scope**: Single crawler instance, 100+ app screens per session

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **MCP-First Architecture**: Plan routes all actions through MCP server, no direct Appium in crawler. PASS
- **Agent-Driven Decision Making**: Agent solely decides actions, MCP executes. PASS
- **Test-First and Observability**: Contract tests for MCP, logging required. PASS
- **Integration and Protocol Compliance**: FASTMCP protocol versioned, contract-tested. PASS
- **Simplicity and Extensibility**: Modular adapters, minimal coupling. PASS

**Gate Status**: PASS (no violations)

## Project Structure

### Documentation (this feature)

```text
specs/001-mcp-server-integration/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
traverser_ai_api/
├── __init__.py
├── main.py
├── cli/
│   ├── __init__.py
│   ├── main.py
│   └── parser.py
├── core/
│   ├── __init__.py
│   ├── adapters.py
│   ├── controller.py
│   └── validation.py
├── agent_assistant.py
├── agent_tools.py
├── ai_assistant.py
├── app_context_manager.py
├── appium_driver.py
├── cli_controller.py
├── config.py
├── crawler.py
├── database.py
├── find_app_info.py
├── generate_paper_tables.py
├── main.py
├── model_adapters.py
├── openrouter_models.py
├── screen_state_manager.py
├── screenshot_annotator.py
├── traffic_capture_manager.py
├── ui_controller.py
├── user_config.json
├── utils.py
└── __pycache__/

tests/
├── __init__.py
├── conftest.py
├── cli/
│   ├── __init__.py
│   ├── test_entrypoint.py
│   ├── test_legacy_migration.py
│   └── test_parser.py
├── services/
└── __pycache__/

removed_appium_code/
├── action_executor.py
├── action_mapper.py
├── agent_tools.py
├── app_context_manager.py
├── appium_driver.py
├── README.md
└── screen_state_manager.py

docs/
├── INSTALLATION_AND_CLI_GUIDE.md
└── SOFTWARE_ARCHITECTURE_DOCUMENTATION.md

ui_monkey/
└── ui_monkey.py
```

**Structure Decision**: Single Python project with modular structure. Core logic in traverser_ai_api/, tests separate, removed code isolated.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
