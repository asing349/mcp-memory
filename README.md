# MCP Memory: A Personal Memory Assistant

MCP Memory is a high-performance, intelligent service for storing and recalling text-based information. It acts as a personal "second brain," allowing you to save notes, snippets, and other data and retrieve it using natural language search. The system is built with a modern AI stack and is instrumented for performance.

## Features

- **Intelligent Storage:** When you save a "memory," the system automatically extracts keywords, assigns a category, and calculates a SimHash to detect near-duplicates.
- **Hybrid Search:** Combines semantic (vector) search with traditional keyword (full-text) search using Reciprocal Rank Fusion (RRF) to deliver highly relevant results.
- **Lifecycle Management:** Store, recall, and forget memories with simple API calls.
- **Automated Maintenance:** An optional background worker handles TTL expiration, de-duplication of similar entries, and database optimization.
- **Performance Metrics:** The API provides detailed latency breakdowns for retrieval operations, allowing for easy performance monitoring.

## Tech Stack

- **Backend:** Python with FastAPI for a high-performance, asynchronous REST API.
- **Database:** SQLite, supercharged with:
    - **`sqlite-vec`** for efficient vector similarity search.
    - **FTS5** for robust full-text search.
- **Caching:** Redis is used as a low-latency cache for embeddings and query results to accelerate repeated searches.
- **AI/NLP:** `sentence-transformers` is used to generate high-quality vector embeddings for semantic understanding.
- **Core Libraries:** `pydantic` for settings management, `aiosqlite` for async database access, and `structlog` for structured logging.

## Getting Started

Here is how you can set up and run the MCP Memory service on your local machine.

### Prerequisites

- Python 3.9+
- Redis server running on `localhost:6379` (or configure the URL).

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd mcp-memory
    ```

2.  **Create a virtual environment and install dependencies:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
    *(Note: A `requirements.txt` file would need to be generated with `pip freeze > requirements.txt`)*

### Configuration

The service can be configured via environment variables. The available options are defined in `src/mcp_memory/config.py`.

- `MCP_MEMORY_DB_PATH`: Path to the SQLite database file. (Default: `~/.mcp/memory.db`)
- `MCP_MEMORY_REDIS_URL`: URL for the Redis cache. (Default: `redis://localhost:6379/0`)
- `MCP_MEMORY_EMBEDDING_MODEL`: The `sentence-transformers` model to use. (Default: `all-MiniLM-L6-v2`)
- `MCP_MEMORY_ENABLE_BACKGROUND`: Set to `true` to enable the background worker. (Default: `false`)

### Running the Server

Once installed, you can run the FastAPI server using `uvicorn`:

```bash
uvicorn mcp_memory.server:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## API Usage

You can interact with the service using any HTTP client, such as `curl`.

### Store a Memory

```bash
curl -X POST http://127.0.0.1:8000/tools/store_memory \
  -H 'Content-Type: application/json' \
  -d '{"content": "The quick brown fox jumps over the lazy dog."}'
```

### Recall Memories

```bash
curl -X POST http://127.0.0.1:8000/tools/recall_memory \
  -H 'Content-Type: application/json' \
  -d '{"query": "jumping fox", "limit": 5}' | jq
```

### Forget a Memory

To forget a memory, you first need its ID (from a recall). You can then delete it by ID.

```bash
curl -X POST http://127.0.0.1:8000/tools/forget_memory \
  -H 'Content-Type: application/json' \
  -d '{"memory_id": "<your-memory-id>", "confirm": true}'
```

### Check Memory Health

```bash
curl http://127.0.0.1:8000/tools/memory_health | jq
```

## Connecting with MCP Clients (e.g., Claude Desktop)

In addition to the FastAPI server, this project includes an MCP (Modular Command Protocol) server for direct integration with compatible clients like the Claude desktop app. This allows you to use the memory tools directly within your AI assistant.

### Running the MCP Server

The MCP server communicates over standard input/output (stdio). To run it, first ensure you have installed the project dependencies in your virtual environment. It's recommended to install the project in editable mode to ensure the module is correctly recognized:

```bash
pip install -e .
```

Then, you can run the MCP server with the following command:

```bash
python -m src.mcp_memory.mcp_server
```

### Connecting the Tool

In your MCP client (e.g., the Claude desktop app), you would typically navigate to the settings for custom tools or agents. Add a new tool and provide the full command to execute the server.

For example, you might configure the tool with a command like:

```
/path/to/your/project/.venv/bin/python -m src.mcp_memory.mcp_server
```

Make sure to use the absolute path to the Python executable within your project\'s virtual environment to ensure it runs with the correct dependencies. Once configured, the `store_memory`, `recall_memory`, and other tools will become available within your client.
