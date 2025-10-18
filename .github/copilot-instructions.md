
---

### Copilot Code Editing Guidelines


   * Leave as much of the system untouched as possible.
   * Don’t rebuild what already works.

   * If unsure, request clarification instead of assuming broader changes.   * Example: *“I can update line 42 as requested. Do you also want related functions updated?”*

   * Note potential improvements without implementing them. * Example: *“I updated function X. Functions Y and Z may need similar changes later.”*

   * Keep functions small and focused.

    * Follow existing project conventions.
    * Reuse existing libraries unless there’s a strong reason not to.

    * Use proper error handling (try-catch, error codes, specific exceptions).
    * Provide clear error messages.
    * Sanitize user input.
    * Don’t hardcode secrets; use environment variables or config tools.
 
14. **Add Necessary Documentation**

    * Comment complex logic or assumptions.
    * Use standard doc formats (e.g., JSDoc, DocStrings).

---

* Do **not** guess or fill gaps. Ask for clarification instead.

---

### Project-specific rules: appium-traverser-master-arbeit

Use these concrete rules when editing this repo so changes align with the crawler’s contracts and runtime behavior.

- Keep stdout prefixes stable: `UI_STATUS:`, `UI_STEP:`, `UI_ACTION:`, `UI_SCREENSHOT:`, `UI_ANNOTATED_SCREENSHOT:`, `UI_FOCUS:`, `UI_END:`. Do not rename or reformat; external UIs parse these.
- AI JSON output contract (see `traverser_ai_api/agent_assistant.py`):
   - Keys: `action`, `target_identifier`, `target_bounding_box`, `input_text`, `reasoning`, `focus_influence`.
   - `target_identifier` must be a single raw attribute value only: either resource-id like `com.pkg:id/name`, or content-desc, or visible text. Do not include `id=`/`content-desc=` prefixes and never combine with `|`.
   - `target_bounding_box` must be an object: `{ "top_left": [y, x], "bottom_right": [y, x] }` using absolute pixels or normalized 0..1. Do not use string formats like `[x,y][x2,y2]`. Use null if not applicable.
   - Example (valid):
      ```json
      {
         "action": "click",
         "target_identifier": "com.example:id/continue",
         "target_bounding_box": {"top_left": [420, 80], "bottom_right": [520, 280]},
         "input_text": null,
         "reasoning": "Primary progression CTA",
         "focus_influence": ["onboarding", "progression"]
      }
      ```
- Element finding priorities (see `crawler.py` and `action_mapper.py`): try in order: ID (full resource-id or package-prefixed), Accessibility ID, text/content-desc (case-insensitive), class contains. Heavier XPath strategies (`xpath_contains`, `xpath_flexible`) are included only when `DISABLE_EXPENSIVE_XPATH` is False. Respect `ELEMENT_STRATEGY_MAX_ATTEMPTS` caps.
- Mapping and fallbacks:
   - Prefer element-based actions when `target_identifier` resolves. If not found and `USE_COORDINATE_FALLBACK` is True, fall back to bbox center tap; clamp to screen bounds.
   - Long press maps to a tap-and-hold at element/bbox center; default duration from `LONG_PRESS_MIN_DURATION_MS`.
   - Input flow must verify focus before typing; if native send_keys fails, ADB text fallback is controlled by `USE_ADB_INPUT_FALLBACK`.
   - Before non-input actions, hide keyboard when `AUTO_HIDE_KEYBOARD_BEFORE_NON_INPUT` is True. Respect toast overlays; wait up to `TOAST_DISMISS_WAIT_MS`.
- Tap safety (see `appium_driver.py`): honor `SAFE_TAP_MARGIN_RATIO` and `SAFE_TAP_EDGE_HANDLING` (`snap` or `reject`) when computing coordinate taps.
- Loop/no-op control (see `crawler.py`):
   - After `MAX_CONSECUTIVE_NO_OP_FAILURES`, select next from `FALLBACK_ACTIONS_SEQUENCE`.
   - Limit repeats per screen via `MAX_SAME_ACTION_REPEAT`; set `last_action_feedback_for_ai` to force different actions.
- Provider/image/XML settings (see `config.py`):
   - `ENABLE_IMAGE_CONTEXT` may be auto-toggled based on `AI_PROVIDER_CAPABILITIES`; don’t hardcode image-on assumptions.
   - `XML_SNIPPET_MAX_LEN` auto-adjusts by provider; use `utils.simplify_xml_for_ai(...)` and per-screen cache keyed by hash/provider/limit.
   - Screenshot preprocessing uses `IMAGE_MAX_WIDTH`, `IMAGE_FORMAT`, `IMAGE_QUALITY`, and optional top/bottom bar cropping; adapters handle final encoding.
- Do not break path templates or persistence: `Config` resolves and persists paths (session dirs, `OUTPUT_DATA_DIR` template, app_info cache). When adding settings, wire them into `Config._get_user_savable_config()` if they’re user-facing.
- Maintain adapter boundaries: implement model-specific logic inside `model_adapters.py`; keep `AgentAssistant` provider-agnostic.
- Tests/docs: when changing public behavior, add a brief note in README or docs and, if feasible, a minimal test harness under `tests/` replicating the JSON contract and mapping edge cases.


