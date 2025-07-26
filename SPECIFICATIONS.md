
---

### 2. The Specifications File (`SPECIFICATIONS.md`)

This is the deep-dive document. It explains *how* the system works, detailing the purpose of each component, the logic flow, and key design decisions. This is the "in case my heart explodes" document.

```markdown
# Technical Specifications: Tennis AI Chatbot

## 1. Introduction

This document provides a detailed technical overview of the Tennis AI Chatbot backend. Its purpose is to serve as a guide for developers maintaining or extending the application. The system is a Python-based FastAPI application that leverages the Google Gemini LLM's tool-calling feature to provide accurate, context-aware answers to tennis-related questions by integrating with a third-party Tennis API.

## 2. Core Component Deep Dive

### `main.py`
- **Purpose**: The main entry point for the application.
- **Responsibilities**:
    - Initializes the `FastAPI` app instance with metadata (title, version).
    - Configures basic root logging for the application.
    - Includes the `chat_router` from `api.routers.chat` to make its endpoints available.
    - Defines a root `/` health check endpoint.
    - Contains the `if __name__ == "__main__"` block to launch the `uvicorn` ASGI server for development.

### `config.py`
- **Purpose**: To manage all application configuration and secrets.
- **Implementation**:
    - Uses `pydantic-settings` to create a `Settings` class that automatically reads variables from a `.env` file.
    - Uses `python-dotenv` to ensure `.env` file variables take precedence over system environment variables.
    - **Crucially, it makes settings like `GOOGLE_API_KEY`, `TENNIS_API_KEY`, and `TENNIS_API_HOST` mandatory. The application will fail to start if they are not defined in `.env`**, which prevents accidental deployment with missing configuration.
    - Exports a singleton `settings` instance for use throughout the application.

### `api/routers/chat.py`
- **Purpose**: The web layer. It defines the external-facing API endpoint.
- **Responsibilities**:
    - Creates a FastAPI `APIRouter`.
    - Defines the `POST /api/chat` endpoint.
    - Uses Pydantic models from `schemas.chat_schemas` for automatic request body validation (`ChatRequest`) and response serialization (`ChatResponse`).
    - Receives the user's query and delegates all business logic to `core.llm_processor.process_chat_request`.
    - Implements top-level error handling, catching any unexpected exceptions from the core logic and returning a generic 500 Internal Server Error to the client.

### `core/llm_processor.py`
- **Purpose**: The "brain" of the application. It orchestrates the entire tool-calling loop with the Gemini model.
- **Key Logic Flow**:
    1.  **Initialization**: The Gemini model is configured with the `GOOGLE_API_KEY` and the list of `GEMINI_TOOLS` from `tool_definitions.py`.
    2.  **Request Processing**: The `process_chat_request` function receives the request from the API layer.
    3.  **Chat Loop**: It enters a loop (max 5 turns to prevent infinite loops).
        a.  The user's query (or the result from a previous tool call) is sent to `chat.send_message_async`.
        b.  The response is inspected. If it contains `.text`, the model has generated a final answer, which is returned immediately.
        c.  If the response contains a `function_call` in its parts, the model wants to use a tool.
        d.  The function name and arguments are extracted.
        e.  The function name is used as a key to look up the actual Python function in the `TOOL_REGISTRY` (`core.tool_definitions.py`).
        f.  The Python function is executed with the arguments provided by the model.
        g.  The return value (the `tool_output`) is wrapped in a specific format and becomes the `prompt` for the next iteration of the loop.
    4.  **History Management**: The Pydantic-based conversation history is converted into the format required by the Gemini `start_chat` method.
    5.  **Error Handling**: If an unknown tool is requested or a tool execution fails, a structured error message is returned.

### `core/tool_definitions.py`
- **Purpose**: To define the interface between our Python code and the Gemini model.
- **Implementation**:
    - **`GEMINI_TOOLS`**: A list of `Tool` objects, where each tool is defined using a `FunctionDeclaration`. The `description` and `parameters` schema within each declaration are **critical**, as this is the information the LLM uses to decide which tool to call and with what arguments.
    - **`TOOL_REGISTRY`**: A simple Python dictionary that maps the string name of a tool (e.g., `"get_live_events"`) to the actual, callable Python function (e.g., `services.tennis_api_client.get_live_events`). This registry is used by the `llm_processor` to execute the tool requested by the model.

### `services/tennis_api_client.py`
- **Purpose**: A dedicated module for all interactions with the external Tennis API.
- **Responsibilities**:
    - **Request Abstraction**: The `_make_request` function centralizes all `requests.get` calls. It automatically adds the required API key headers, sets a timeout, and handles HTTP/network errors gracefully, returning a structured error dictionary.
    - **Data Simplification**: The `_process_event_list` function takes the raw, verbose JSON from the API and transforms it into a cleaner, more concise summary format. This is crucial for sending only relevant information back to the LLM, saving tokens and reducing noise.
    - **Tool Implementations**: Contains the actual Python functions that implement the logic for each tool (e.g., `get_scheduled_events_by_date`, `get_rankings`).
    - **Complex Logic (`get_h2h_events`)**: This function demonstrates a robust, multi-step process to find head-to-head data, as the API does not provide a direct endpoint for it. It attempts multiple strategies (player search, checking recent match history, scanning a 24-month calendar) before giving up and triggering the web search fallback.

### `services/web_search_client.py`
- **Purpose**: To provide a fallback data source when the Tennis API is insufficient.
- **Implementation**:
    - Uses the `requests` and `BeautifulSoup4` libraries to perform a live web scrape of DuckDuckGo's simple HTML interface.
    - This approach is self-contained and **does not require a third-party search API key**.
    - It extracts the top search result snippets, combines them into a single context string, and returns this context. The LLM is then expected to summarize this context to answer the user's original query.

## 3. Tool Functionality Details

| Tool Name (for LLM)          | Description & Purpose                                                                                             | Parameters                                     | Python Function Called                 |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- | -------------------------------------- |
| `get_scheduled_events_by_date` | Fetches all tennis matches for a given date.                                                                      | `date: str` ('today', 'tomorrow', 'YYYY-MM-DD')  | `get_scheduled_events_by_date`         |
| `get_live_events`            | Fetches all tennis matches that are currently in progress.                                                        | (None)                                         | `get_live_events`                      |
| `get_odds_by_date`           | Fetches betting odds for matches on a given date.                                                                 | `date: str` ('today', 'tomorrow', 'YYYY-MM-DD')  | `get_odds_by_date`                     |
| `get_event_statistics`       | Gets detailed stats for a *single* match. Requires an `event_id` found from other tools.                          | `event_id: str`                                | `get_event_statistics`                 |
| `get_player_performance`     | Gets recent match history for a player. Requires a `player_id`.                                                   | `player_id: str`                               | `get_player_performance`               |
| `get_h2h_events`             | Finds head-to-head match history between two players by name.                                                     | `player1_name: str`, `player2_name: str`       | `get_h2h_events`                       |
| `get_rankings`               | Fetches official world rankings for men (ATP) or women (WTA).                                                     | `ranking_type: str` ('atp' or 'wta')           | `get_rankings`                         |
| `perform_web_search`         | Fallback for general info, news, or when other tools fail.                                                        | `query: str`                                   | `perform_web_search`                   |
| `debug_api_search`           | (For Debugging) Directly queries the API's player search endpoint to see the raw output.                            | `player_name: str`                             | `debug_api_search`                     |

## 4. Potential Future Enhancements

- **Caching**: Implement caching (e.g., with Redis) for API responses like rankings or daily schedules that do not change frequently, reducing API costs and latency.
- **Asynchronous Tool Execution**: The current tool execution is synchronous. For tools involving I/O (all of them), converting `services` functions to `async def` and `await`ing them would improve server concurrency.
- **Streaming Responses**: Modify the `/api/chat` endpoint to stream the final LLM response token-by-token for better perceived performance on the client-side.
- **Advanced Logging & Tracing**: Integrate a structured logging library and a tracing tool (like OpenTelemetry) to better monitor requests as they flow through the system (LLM -> Tool -> LLM).