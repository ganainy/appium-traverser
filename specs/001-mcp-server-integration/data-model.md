# Data Model: MCP Server Integration

## Entities

### Agent
- **Description**: Decides and sends actions to the MCP server. Maintains state, history, and reasoning context.
- **Fields**:
  - id: string
  - session_id: string
  - state: object
  - history: list of actions
  - reasoning_context: object

### MCP Server
- **Description**: Receives actions from the agent, translates them to device commands (via Appium), and returns results. Implements the FASTMCP protocol.
- **Fields**:
  - id: string
  - protocol_version: string
  - connected_devices: list of device ids
  - session_id: string
  - logs: list of events

### Action
- **Description**: A structured message (e.g., tap, input, scroll) sent from the agent to the MCP server, including parameters and expected outcomes.
- **Fields**:
  - id: string
  - type: enum (tap, input, scroll, etc.)
  - target_identifier: string (single raw attribute: resource-id, content-desc, or text)
  - target_bounding_box: object {top_left: [y,x], bottom_right: [y,x]} (absolute pixels or normalized)
  - input_text: string (optional)
  - timestamp: datetime
  - session_id: string

### Session
- **Description**: Represents an active automation session, including device info, state, and logs.
- **Fields**:
  - id: string
  - device_info: object
  - start_time: datetime
  - end_time: datetime (nullable)
  - state: object
  - logs: list of events

### Device
- **Description**: Android device or emulator connected to MCP server
- **Fields**:
  - id: string
  - platform: string (Android)
  - version: string
  - capabilities: object
  - session_id: string (current session)

## Relationships
- Agent 1..* — 1 Session
- Session 1 — * Action
- MCP Server 1 — * Session
- MCP Server 1 — * Action
- Session 1 — 1 Device
- MCP Server 1 — * Device

## Validation Rules
- All actions must reference a valid session_id
- Only the agent may initiate actions
- MCP server must log all received actions and results
- Session must be closed (end_time set) before logs are archived
