# Feature Specification: Preserve Complete Removed Code

## Feature Short Name
preserve-complete-removed-code

## Overview
When Appium-related code is removed from the main codebase as part of the MCP migration, the full, original code must be preserved in the `removed_appium_code/` directory. These preserved files must contain the complete, unmodified code (not placeholders or stubs) to ensure developers can reference or restore any removed logic as needed.

## User Scenarios
- When a developer removes Appium-related files or logic, the entire original file is copied to `removed_appium_code/`.
- The copied file contains the full, original code, including all classes, methods, and comments.
- Developers can open any file in `removed_appium_code/` and see the full legacy implementation for reference or copy-paste.

## Functional Requirements
1. When removing Appium-related files or logic, copy the entire original file to `removed_appium_code/`.
2. The copied file must contain the full, original code, including all classes, methods, and comments.
3. Placeholders or stubs are not permitted in these preserved files.
4. The process must be repeatable for any number of files.
5. The preserved files must be git-ignored.

## Success Criteria
- 100% of files in `removed_appium_code/` contain the full, original code.
- No file in `removed_appium_code/` contains only a placeholder or stub.
- Developers can copy-paste any removed logic from these files without missing context.
- The process is documented and verifiable by code review.

## Key Entities
- Removed Appium-related files
- `removed_appium_code/` directory

## Assumptions
- Only Appium-related files are subject to this process.
- The process is part of a larger migration to MCP.

## Dependencies
- MCP migration plan and tasks
- .gitignore configuration for `removed_appium_code/`

## Out of Scope
- Migration of non-Appium-related files
- Implementation details of how files are copied

## Revision History
- 2025-10-30: Initial specification created

# Feature Specification: MCP Server Integration

**Feature Branch**: `001-mcp-server-integration`  
**Created**: 2025-10-30  
**Status**: Draft  
**Input**: Integrate Appium MCP server (FASTMCP) as the exclusive automation backend. The AI agent will decide and send actions to the MCP server, which will handle all real device interactions. Remove all direct Appium logic from the crawler. Ensure all documentation and architecture reflect this MCP-first, agent-driven approach.

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
  
  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->


### User Story 1 - Agent-Driven Automation (Priority: P1)

As a developer or tester,
I want the AI agent to decide all app actions and send them to the MCP server for execution,
so that all device interactions are routed through a single, protocol-compliant backend.

**Why this priority**: This is the core of the migration; without it, the MCP-first architecture is not realized.

**Independent Test**: Run a crawl session and verify that all actions (tap, input, scroll, etc.) are sent as MCP protocol messages and executed by the MCP server, with no direct Appium calls in the crawler codebase.

**Acceptance Scenarios**:
1. **Given** the crawler is started, **When** the agent decides to tap a button, **Then** the action is sent to the MCP server and executed on the device.
2. **Given** the agent decides to input text, **When** the action is sent, **Then** the MCP server performs the input and returns the result to the agent.

---

### User Story 2 - Remove Direct Appium Logic (Priority: P2)


As a maintainer,
I want all direct Appium logic removed from the crawler,
and the removed code to be moved to a separate, git-ignored folder,
so that the only automation interface is the MCP protocol and server, but I can still access the old Appium code later to improve the MCP server if needed.

**Why this priority**: Ensures architectural clarity, maintainability, and protocol compliance.


**Independent Test**: 
1. Search the codebase for Appium driver usage outside the MCP adapter/server; none should exist. All device actions must be routed through the MCP server.
2. Verify that the removed Appium code is present in a separate, git-ignored folder for future reference.

**Acceptance Scenarios**:
1. **Given** the codebase, **When** searching for Appium driver usage, **Then** only the MCP server/adapter contains such logic.
2. **Given** a new device action, **When** implemented, **Then** it is added to the MCP protocol and not as a direct Appium call.
3. **Given** the removed Appium code, **When** reviewing the repository, **Then** it is found in a separate, git-ignored folder for future MCP server improvements.

---

### User Story 3 - Documentation and Architecture Update (Priority: P3)

As a user or contributor,
I want all documentation and architecture diagrams to reflect the MCP-first, agent-driven approach,
so that onboarding and maintenance are clear and up-to-date.

**Why this priority**: Prevents confusion and ensures new contributors follow the correct architecture.

**Independent Test**: Review README and architecture docs; all references to direct Appium usage are removed or replaced with MCP server integration instructions.

**Acceptance Scenarios**:
1. **Given** the documentation, **When** following setup and usage instructions, **Then** the MCP server is the only automation backend described.
2. **Given** architecture diagrams, **When** reviewed, **Then** they show the agent sending actions to the MCP server, not to Appium directly.

---


### Edge Cases

- What happens if the MCP server is unavailable or crashes during a crawl session?
- How does the system handle unsupported actions or protocol errors from the MCP server?
- What if the agent sends an invalid or malformed action?
- How are timeouts and retries managed between the agent and MCP server?

## Requirements *(mandatory)*

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right functional requirements.
-->


### Functional Requirements

- **FR-001**: The crawler MUST route all device actions (tap, input, scroll, etc.) through the MCP server using the FASTMCP protocol.
- **FR-002**: The AI agent MUST be the sole decision-maker for all automation actions; no hardcoded automation logic is allowed outside the agent or MCP server.
- **FR-003**: All direct Appium driver usage MUST be removed from the crawler codebase, except within the MCP server/adapter.
- **FR-004**: The system MUST handle MCP server errors, timeouts, and protocol failures gracefully, with clear error reporting and retry logic.
- **FR-005**: Documentation and architecture diagrams MUST be updated to reflect the MCP-first, agent-driven approach.
- **FR-006**: The system MUST support extensibility for new MCP protocol actions and agent capabilities without breaking existing functionality.


### Key Entities

- **Agent**: Decides and sends actions to the MCP server. Maintains state, history, and reasoning context.
- **MCP Server**: Receives actions from the agent, translates them to device commands (via Appium), and returns results. Implements the FASTMCP protocol.
- **Action**: A structured message (e.g., tap, input, scroll) sent from the agent to the MCP server, including parameters and expected outcomes.
- **Session**: Represents an active automation session, including device info, state, and logs.

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.

### Functional Requirements

- **FR-001**: The crawler MUST route all device actions (tap, input, scroll, etc.) through the MCP server using the FASTMCP protocol.
- **FR-002**: The AI agent MUST be the sole decision-maker for all automation actions; no hardcoded automation logic is allowed outside the agent or MCP server.
- **FR-003**: All direct Appium driver usage MUST be removed from the crawler codebase, except within the MCP server/adapter.
- **FR-004**: After removal, all direct Appium code MUST be moved to a separate, git-ignored folder within the repository, so it can be referenced later for MCP server improvements.
- **FR-005**: The system MUST handle MCP server errors, timeouts, and protocol failures gracefully, with clear error reporting and retry logic.
- **FR-006**: Documentation and architecture diagrams MUST be updated to reflect the MCP-first, agent-driven approach.
- **FR-007**: The system MUST support extensibility for new MCP protocol actions and agent capabilities without breaking existing functionality.
