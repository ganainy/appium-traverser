
# Tasks: MCP Server Integration

## Phase 1: Setup
- [X] T001 Create git-ignored folder for removed Appium code in removed_appium_code/
- [X] T002 Install Python 3.8+, Node.js 18+, Appium 2.0+, and FASTMCP dependencies
- [X] T003 Initialize MCP server and verify connectivity with crawler
- [X] T004 [P] Install all Python and Node.js dependencies (requirements.txt, MCP server)

## Phase 2: Foundational
- [X] T005a Identify all files in traverser_ai_api/ with direct Appium or AppiumDriver usage (imports, instantiations, config)
- [X] T005b For each identified file, move Appium-specific logic to removed_appium_code/ and replace with MCP server calls or stubs
- [X] T005c Refactor traverser_ai_api/agent_assistant.py to ensure all device actions are routed through the MCP server only
- [X] T005d Refactor traverser_ai_api/appium_driver.py to remove or isolate all direct Appium driver logic
- [X] T005e Update or remove Appium-related config in traverser_ai_api/config.py and user_config.json
- [X] T005f Remove or update Appium-related docstrings, comments, and error messages in traverser_ai_api/
- [X] T005g Run static analysis to verify no direct Appium usage remains outside the MCP server/adapter
- [X] T006 Move removed Appium code to removed_appium_code/ and update .gitignore
- [X] T007 [P] Update configuration to route all device actions through MCP server (config.py, traverser_ai_api/config.py)
- [X] T008 [P] Add contract tests for MCP protocol compliance in tests/contract/

## Phase 3: User Story 1 - Agent-Driven Automation (P1)
- [X] T009 [US1] Implement agent logic to decide and send all actions to MCP server (traverser_ai_api/agent_assistant.py)
- [X] T010 [P] [US1] Ensure all device actions (tap, input, scroll, etc.) are sent as MCP protocol messages (traverser_ai_api/agent_assistant.py)
- [X] T011 [US1] Log and trace all agent decisions and MCP actions (traverser_ai_api/agent_assistant.py, traverser_ai_api/appium_driver.py)
- [X] T012 [US1] Add integration tests to verify all actions are routed through MCP server (tests/integration/)

## Phase 4: User Story 2 - Remove Direct Appium Logic (P2)
- [X] T013 [US2] Search codebase for Appium driver usage outside MCP server/adapter and remove (traverser_ai_api/)
- [X] T014 [US2] Verify all device actions are routed through MCP server (static analysis, code review)
- [X] T015 [US2] Document location and usage of removed Appium code in removed_appium_code/README.md
- [X] T016 [US2] Add test to ensure new device actions are added to MCP protocol, not as direct Appium calls (tests/contract/)

## Phase 5: User Story 3 - Documentation and Architecture Update (P3)
- [X] T017 [US3] Update README and architecture docs to reference MCP server as the only automation backend (README.md, docs/SOFTWARE_ARCHITECTURE_DOCUMENTATION.md)
- [X] T018 [US3] Update architecture diagrams to show agent → MCP server flow (docs/SOFTWARE_ARCHITECTURE_DOCUMENTATION.md)
- [X] T019 [US3] Remove or update all references to direct Appium usage in documentation (README.md, docs/INSTALLATION_AND_CLI_GUIDE.md)

## Final Phase: Polish & Cross-Cutting Concerns
- [X] T020 Review and clean up codebase for MCP-first, agent-driven compliance
- [X] T021 [P] Add final integration and regression tests for crawl sessions (tests/integration/)
- [X] T022 [P] Validate all documentation and onboarding instructions are up to date

## Dependencies
- Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1) → Phase 4 (US2) → Phase 5 (US3) → Final Phase (Polish)

## Parallel Execution Examples
- T004, T007, T008, T010, T021, T022 can be executed in parallel with other tasks in their respective phases

## Implementation Strategy
- MVP: Complete all tasks for User Story 1 (T009–T012) to deliver a working agent-driven MCP integration
- Incremental delivery: Complete each user story phase independently and validate with tests and documentation
