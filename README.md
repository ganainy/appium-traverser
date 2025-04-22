# AI-Driven Android App Crawler

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-development-orange.svg)]() 

## Overview

This project implements an automated crawler for Android applications driven by a multimodal AI model (Google Gemini). It intelligently explores app screens by analyzing visual layout (screenshots) and structural information (XML), deciding the next best action to take (click, input, scroll, back) to discover new states and interactions.

The crawler maintains a state graph, uses visual and structural hashing to identify unique screens, detects visually similar screens to reduce redundancy, and incorporates loop detection to avoid getting stuck. It logs discovered screens and transitions to a persistent SQLite database and saves screenshots for review.

## Features

*   **AI-Powered Exploration:** Uses Google Gemini (Flash or Pro models) to analyze screen context (screenshot + simplified XML) and decide the next action.
*   **Appium Integration:** Leverages Appium (via `appium-python-client`) to interact with the target Android application (real device or emulator).
*   **State Management:**
    *   Identifies unique screen states using a combination of XML structure hash and visual perceptual hash (pHash).
    *   Detects visually similar screens using hash distance to merge redundant states.
    *   Stores discovered screens and transitions in an SQLite database.
*   **Robust Interaction:**
    *   Handles common actions: `click`, `input` (with validation for editable fields), `scroll_up`, `scroll_down`, `back`.
    *   Dynamically prioritizes element finding strategies (ID, Accessibility ID, XPath) based on success rate.
    *   Attempts recovery actions (back press, app relaunch) if interaction fails or the crawler loses context.
*   **Loop Detection:** Tracks screen visit counts within a run and instructs the AI to prioritize new paths if a screen is visited too often.
*   **Configuration:** Centralized configuration file (`config.py`) for easy setup of target app, device, AI model, crawl limits, etc.
*   **Context Awareness:**
    *   Optionally uses chat memory (Gemini history) for more contextually relevant AI decisions.
    *   Provides AI with history of actions taken from the current screen.
    *   Allows specifying external packages (e.g., browsers, Google Play Services) that the crawler can interact with during flows like login or webviews.
*   **Visualization:**
    *   Saves raw screenshots of each unique discovered screen state.
    *   Optionally saves annotated screenshots indicating the AI's target bounding box for `click`/`input` actions.
*   **Extensibility:** Modular design allows for easier modification or addition of new actions, AI models, or interaction logic.

## How it Works

1.  **Initialization:** Connects to Appium server, loads configuration, connects to the database, and initializes the state manager (loading previous state if configured).
2.  **Get Current State:** Takes a screenshot and retrieves the XML page source of the current screen.
3.  **Hashing & State Check:** Calculates the XML hash and visual hash. The `StateManager` checks if this exact state (or a visually similar one) has been seen before using the database and in-memory state. It returns the definitive `ScreenRepresentation` for the current state.
4.  **Visit Count & History:** Increments the visit count for the current screen state (for loop detection) and retrieves the history of actions already attempted from this state during the current run.
5.  **AI Analysis:** Sends the screenshot, simplified XML, action history, visit count, and available actions to the Gemini AI model.
6.  **AI Action Suggestion:** The AI returns a suggested action (e.g., `click`, `input`, `scroll`) and target details (identifier, bounding box, input text) in JSON format.
7.  **Action Mapping:** The crawler attempts to map the AI's target identifier to a specific `WebElement` using various strategies (ID, Accessibility ID, XPath). It validates that `input` actions target editable fields.
8.  **Action Execution:** Executes the mapped action using the Appium driver.
9.  **Record Transition:** Records the transition from the previous state to the current state, including the action taken, in the database and updates the in-memory action history.
10. **Wait & Repeat:** Waits briefly for the UI to settle and repeats the loop from Step 2.
11. **Termination:** The crawl stops when it reaches the configured maximum steps or duration, or if it encounters too many consecutive failures (AI, mapping, execution).

## Architecture / Components

*   **`main.py`:** Entry point. Sets up logging, handles configuration checks, initializes and runs the `AppCrawler`.
*   **`crawler.py`:** Orchestrates the crawling process, integrating all other components. Manages the main loop, state transitions, action mapping, and execution.
*   **`appium_driver.py`:** Wrapper class for Appium WebDriver interactions (connect, disconnect, find element, click, input, scroll, screenshot, page source, ADB commands, etc.).
*   **`ai_assistant.py`:** Handles communication with the Google Gemini API. Builds prompts, sends requests, parses JSON responses, and manages optional chat history.
*   **`state_manager.py`:** Manages the representation of discovered screens (`ScreenRepresentation`) and transitions. Handles hashing, visual similarity checks, visit counts, action history, and interaction with the database for persistence.
*   **`database.py`:** Manages the SQLite database connection and operations (creating tables, inserting/retrieving screen and transition data).
*   **`utils.py`:** Contains utility functions for hashing (XML, visual), hash distance calculation, XML simplification for AI prompts, and drawing indicators on screenshots.
*   **`config.py`:** Centralized configuration settings for the crawler, Appium, AI, database paths, etc. Reads sensitive keys from `.env`.

## Setup and Installation

Detailed prerequisites, environment configuration, and installation steps are provided in the [SETUP_GUIDE.md](./SETUP_GUIDE.md) file. Please refer to it for a complete guide on setting up the project.


## Output

*   **Database:** An SQLite database file (e.g., `database_output/your_app_package_crawl_data.db`) containing:
    *   `screens` table: Information about each unique screen state discovered (ID, hashes, screenshot path).
    *   `transitions` table: Records of actions taken between screen states.
*   **Screenshots:**
    *   Raw screenshots saved in `screenshots/crawl_screenshots_your_app_package/`.


