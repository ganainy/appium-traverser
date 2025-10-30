# Research Log: MCP Server Integration

## Decision: Performance Goals
- **What was chosen**: Target <500ms added latency per device action routed through MCP server
- **Rationale**: Ensures user-perceived responsiveness and aligns with typical mobile automation expectations. Allows for network and protocol overhead while keeping the system usable for interactive and batch crawls.
- **Alternatives considered**: <200ms (may be unrealistic for remote/cloud devices); <1s (may degrade UX for fast-paced apps)

## Decision: Scale/Scope
- **What was chosen**: Support crawling apps with up to 50 screens per session
- **Rationale**: Covers the vast majority of real-world Android apps and provides a clear upper bound for resource planning and test coverage.
- **Alternatives considered**: Unlimited (risk of resource exhaustion); 10 screens (too restrictive for most apps)

## Decision: Removed Appium Code Handling
- **What was chosen**: Move all removed direct Appium code to a git-ignored folder within the repository
- **Rationale**: Preserves valuable reference code for future MCP server improvements without polluting the main codebase or violating MCP-first principles.
- **Alternatives considered**: Delete code entirely (loss of reference); keep in main repo (violates architecture)

## Decision: Testing Approach
- **What was chosen**: Use pytest for unit/integration, add contract tests for MCP protocol compliance
- **Rationale**: Ensures all new and migrated features are independently testable and protocol-compliant, as required by the constitution.
- **Alternatives considered**: Manual testing only (insufficient for regression and compliance)

## Decision: MCP Protocol Constraints
- **What was chosen**: Strict FASTMCP protocol compliance, JSON-RPC 2.0 over WebSocket
- **Rationale**: Ensures interoperability with MCP ecosystem, version safety. JSON-RPC provides reliable request/response with error handling.
- **Alternatives considered**: REST API (higher latency), custom binary protocol (complexity)

## Decision: Error Handling Strategy
- **What was chosen**: Exponential backoff retries (max 3 attempts), configurable timeouts per action type
- **Rationale**: Robust against transient failures (device lag, network), prevents infinite hangs. Per-action timeouts handle varying complexities (tap vs scroll).
- **Alternatives considered**: Fixed retries (less adaptive), no retries (brittle)

## Decision: Agent-MCP Coupling
- **What was chosen**: Loose coupling via protocol contracts, agent unaware of Appium details
- **Rationale**: Maintains agent portability, allows MCP server evolution without agent changes.
- **Alternatives considered**: Tight coupling (harder to maintain), agent directly imports Appium (violates architecture)
