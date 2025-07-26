    # Tennis AI Chatbot Backend
    
    This repository contains the source code for a specialized AI chatbot backend. The application uses Google's Gemini 1.5 Flash model with Tool Calling capabilities to answer user questions about the world of professional tennis. It integrates with a live Tennis API for real-time data and includes a fallback web search mechanism for broader queries.
    
    ## ✨ Features
    
    - **Conversational AI**: Powered by Google Gemini 1.5 Flash for natural language understanding and generation.
    - **Tool-Based Integration**: Intelligently uses a set of predefined tools to query a live Tennis API for specific data.
    - **Real-Time Data**: Can fetch scheduled matches, live scores, player statistics, H2H records, and official rankings.
    - **Fallback Mechanism**: If the Tennis API cannot answer a query or fails, the system automatically performs a web search as a backup.
    - **Asynchronous API**: Built with FastAPI for high-performance, non-blocking I/O.
    - **Configuration-Driven**: All sensitive keys and environment-specific settings are managed via a `.env` file.
    
    ## 🏗️ System Architecture
    
    The application follows a simple but powerful request-response flow enhanced by the LLM's tool-calling loop:
    
    1.  A `POST` request with a user's query hits the FastAPI `/api/chat` endpoint.
    2.  The `llm_processor` sends the query to the Gemini model, along with a list of available tools.
    3.  Gemini analyzes the query and decides if it needs a tool.
        - **If no tool is needed**, it generates a direct answer, which is returned to the user.
        - **If a tool is needed**, it returns the name of the tool and the arguments to use (e.g., `get_scheduled_events_by_date` with `date='today'`).
    4.  The application executes the corresponding Python function (e.g., makes a request to the Tennis API).
    5.  The data from the tool (API result or web search context) is sent back to Gemini.
    6.  Gemini uses this new context to generate a final, human-readable answer.
    7.  The final answer is returned to the user in the API response.
    
    ## 🚀 Getting Started
    
    Follow these steps to set up and run the project locally.
    
    ### Prerequisites
    
    - Python 3.9+
    - A Git client
    
    ### 1. Clone the Repository
    
    ```bash
    git clone <your-repository-url>
    cd <repository-directory>
    ```
    
    ### 2. Set Up a Virtual Environment
    
    It is highly recommended to use a virtual environment to manage dependencies.
    
    ```bash
    # For Unix/macOS
    python3 -m venv venv
    source venv/bin/activate
    
    # For Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```
    
    ### 3. Install Dependencies
    
    The required Python libraries are listed in `requirements.txt`.
    
    ```bash
    pip install -r requirements.txt
    ```
    
    ### 4. Configure Environment Variables
    
    The application requires API keys and host information to function. Create a file named `.env` in the project root by copying the example file:
    
    ```bash
    # For Unix/macOS
    cp .env.example .env
    
    # For Windows
    copy .env.example .env
    ```
    
    Now, open the `.env` file and fill in the values for the following variables:
    
    ```ini
    # .env file
    
    # --- REQUIRED API KEYS ---
    # Your API key from Google AI Studio
    GOOGLE_API_KEY="YOUR_GOOGLE_GEMINI_API_KEY"
    
    # The API key for the Tennis API from RapidAPI
    TENNIS_API_KEY="YOUR_RAPIDAPI_TENNIS_KEY"
    
    # A security key for administrative or protected endpoints (currently unused but good practice)
    ADMIN_API_KEY="some-secret-admin-key"
    
    # --- REQUIRED API HOST ---
    # The host for the Tennis API on RapidAPI
    TENNIS_API_HOST="tennisapi1.p.rapidapi.com"
    
    # --- OPTIONAL SETTINGS ---
    # Set the application's logging level (DEBUG, INFO, WARNING, ERROR)
    LOG_LEVEL="INFO"
    ```
    
    ### 5. Run the Application
    
    Use `uvicorn` to start the local development server.
    
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    ```
    
    - `--reload` enables hot-reloading for development.
    - The server will be accessible at `http://127.0.0.1:8000`.
    
    ## ⚙️ API Usage
    
    Once the server is running, you can interact with the chatbot via the `/api/chat` endpoint.
    
    ### Interactive API Docs
    
    Navigate to `http://127.0.0.1:8000/docs` in your browser to see the auto-generated Swagger UI documentation, where you can test the endpoint directly.
    
    ### Example `curl` Request
    
    Here is an example of how to send a query using `curl`:
    
    ```bash
    curl -X 'POST' \
      'http://127.0.0.1:8000/api/chat' \
      -H 'accept: application/json' \
      -H 'Content-Type: application/json' \
      -d '{
      "query": "Who is playing tennis today?",
      "history": []
    }'
    ```
    
    **Example Response:**
    
    ```json
    {
      "response": "Today, some of the scheduled matches include Casper Ruud vs. Miomir Kecmanovic in the Hamburg tournament and Peyton Stearns vs. Elisabetta Cocciaretto in the Prague tournament.",
      "sources": [
        "tennis_api_client: get_scheduled_events_by_date"
      ]
    }
    ```
    
    ## 📂 Project Structure
    
    ```
    .
    ├── .env.example          # Template for environment variables
    ├── api/                    # Contains API routing logic
    │   ├── __init__.py
    │   └── routers/
    │       ├── __init__.py
    │       └── chat.py         # Defines the /api/chat endpoint
    ├── config.py             # Handles loading settings from .env
    ├── core/                   # Core application logic
    │   ├── __init__.py
    │   ├── llm_processor.py    # Orchestrates interaction with Gemini and tools
    │   └── tool_definitions.py # Defines tools for the Gemini model
    ├── main.py                 # Main application entry point
    ├── requirements.txt        # Project dependencies
    ├── schemas/                # Pydantic data models (schemas)
    │   ├── __init__.py
    │   └── chat_schemas.py     # Defines request/response models
    └── services/               # Handles external service integrations
        ├── __init__.py
        ├── tennis_api_client.py # Functions to call the Tennis API
        └── web_search_client.py # Fallback web scraping function
    ```
    
    ## 📄 License
    
    This project is licensed under the MIT License.