export const codebaseCategories = [
  {
    id: 'cli',
    label: 'CLI',
    description: 'Developer command entrypoint and utility workflows for Luna.',
    files: [
      {
        slug: 'luna',
        title: 'cli/luna.mjs',
        path: 'cli/luna.mjs',
        summary: 'Main Luna CLI command dispatcher for running dev, backend, frontend, Electron, and utility workflows.',
        details: [
          'Defines the supported CLI commands and their associated subprocess behavior.',
          'Wraps npm and Python invocation with cross-platform environment normalization.',
          'Implements helper commands: help, doctor, dev, dev:lan, backend, frontend, electron, build, dist, check, processes, clean.',
          'Uses child_process.spawn to delegate to existing package scripts and to preserve interactive stdio.',
          'Provides Python subprocess environment fixes such as PYTHONDONTWRITEBYTECODE and PYTHONUNBUFFERED.',
        ],
      },
    ],
  },
  {
    id: 'electron',
    label: 'Electron',
    description: 'Desktop shell and native integration for Luna.',
    files: [
      {
        slug: 'main',
        title: 'electron/main.js',
        path: 'electron/main.js',
        summary: 'Desktop application shell that starts the backend, opens the UI window, and manages native lifecycle behaviors.',
        details: [
          'Ensures a single app instance and restores the existing window on second launch.',
          'Spawns and monitors the Python backend, including crash recovery and exponential restart backoff.',
          'Implements backend health checks and automatic recovery when the backend becomes unresponsive.',
          'Creates a frameless BrowserWindow with preload scripts and loads developer or production frontend content.',
          'Manages tray menu, window events, and native integrations such as notifications, clipboard, and location.',
        ],
      },
      {
        slug: 'preload',
        title: 'electron/preload.js',
        path: 'electron/preload.js',
        summary: 'Secure renderer bridge exposing native Electron APIs to the frontend.',
        details: [
          'Uses contextBridge to safely expose a narrow set of Electron APIs to the browser UI.',
          'Provides window control commands, native notifications, clipboard access, and OAuth popup handling.',
          'Reads the local .env file to make the Luna API key available to the renderer without exposing the full filesystem.',
          'Exposes an API base URL and Electron runtime detection helpers for frontend networking.',
        ],
      },
    ],
  },
  {
    id: 'backend',
    label: 'Backend',
    description: 'API server, runtime services, process registry, and configuration for Luna.',
    files: [
      {
        slug: 'main',
        title: 'backend/main.py',
        path: 'backend/main.py',
        summary: 'FastAPI application bootstrap with lifecycle hooks, middleware, and router registration.',
        details: [
          'Defines a FastAPI app with a lifespan manager that initializes the database and starts scheduler/process lifecycle.',
          'Registers APIKeyMiddleware for optional auth protection on API routes.',
          'Adds CORS middleware and mounts static frontend assets when the production build exists.',
          'Includes routers for chat, memory, calendar, system, voice, Spotify, state, training, sleep, vision, Luna, and agent APIs.',
          'Serves the SPA shell as a fallback route when the frontend is built to disk.',
        ],
      },
      {
        slug: 'server',
        title: 'backend/server.py',
        path: 'backend/server.py',
        summary: 'Standalone backend entrypoint used by Electron to launch the FastAPI server and manage PID cleanup.',
        details: [
          'Configures stdout/stderr encoding and adds the project root to sys.path for subprocess startup.',
          'Writes a PID file so the Electron shell can identify and clean up stale backend processes.',
          'Registers an atexit cleanup handler to remove the PID file on normal shutdown.',
          'Starts Uvicorn with the FastAPI application from backend.main on the configured host and port.',
        ],
      },
      {
        slug: 'config',
        title: 'backend/config.py',
        path: 'backend/config.py',
        summary: 'Application settings and environment configuration using Pydantic BaseSettings.',
        details: [
          'Defines host/port settings, provider selection, model names, and runtime booleans.',
          'Includes default paths for the SQLite DB, Chroma vector store, and frontend dist folder.',
          'Supports both Ollama and OpenAI-compatible provider configuration for chat and embeddings.',
          'Parses debug mode strings flexibly and reads values from .env files with utf-8 encoding.',
          'Ignores extra environment values by default so only known settings are applied.',
        ],
      },
      {
        slug: 'processes-registry',
        title: 'backend/processes/registry.py',
        path: 'backend/processes/registry.py',
        summary: 'Dynamic process registration and lifecycle management for background runtime work.',
        details: [
          'Defines a shared ProcessDef dataclass to describe process metadata and lifecycle hooks.',
          'Discovers registered process modules from a static list and imports them dynamically.',
          'Exposes helpers to list available processes and to start/stop lifecycle-managed processes.',
          'Handles reverse-order shutdown to avoid dependency issues during cleanup.',
          'Supports scheduler-integrated processes and explicit start/stop hooks for runtime behavior.',
        ],
      },
      {
        slug: 'chat-router',
        title: 'backend/routers/chat.py',
        path: 'backend/routers/chat.py',
        summary: 'Chat API route implementation, prompt composition, streaming, and memory orchestration.',
        details: [
          'Defines the /api/chat endpoints for streaming chat, confirmations, and conversation controls.',
          'Builds the system prompt with memory, personality, activity, live data, visual context, and tools.',
          'Integrates core services such as MemoryManager, PersonalityEngine, ActivityTracker, task planner, and visual context.',
          'Streams responses with server-sent-event-like patterns and logs chat output to data/chat.log.',
          'Extracts facts, emotions, and summaries from conversations for memory updates and longer-term context.',
        ],
      },
      {
        slug: 'agent-router',
        title: 'backend/routers/agent.py',
        path: 'backend/routers/agent.py',
        summary: 'Agent and skill management API routes for workspace, browser, permissions, and audit data.',
        details: [
          'Provides endpoints for installed skills, workflow processes, audit history, and tool permissions.',
          'Exposes browser interaction routes for opening URLs, reading pages, and controlling tasks.',
          'Supports workspace file access and write requests in a controlled skill context.',
          'Implements browser status endpoints and handles OAuth-style callbacks for tools like Spotify.',
        ],
      },
    ],
  },
  {
    id: 'frontend',
    label: 'Frontend',
    description: 'Browser UI entrypoints, layout components, and state management for Luna.',
    files: [
      {
        slug: 'main',
        title: 'frontend/src/main.tsx',
        path: 'frontend/src/main.tsx',
        summary: 'React application bootstrap that mounts the Luna UI into the browser DOM.',
        details: [
          'Imports the top-level App component and global styles.',
          'Creates a React root around the #root DOM element and enables strict mode.',
          'Serves as the application entrypoint for Vite and Electron rendering.',
        ],
      },
      {
        slug: 'app',
        title: 'frontend/src/App.tsx',
        path: 'frontend/src/App.tsx',
        summary: 'Top-level React app shell that coordinates auth, view mode, health checks, and main UI views.',
        details: [
          'Detects Electron runtime and handles authentication for browser access.',
          'Loads personality state, health status, and proactive messages from the backend.',
          'Renders the dashboard, voice mode, or the main UI with sidebar and active views.',
          'Uses motion animations and a startup splash while the app initializes.',
          'Switches between chat, memory, calendar, agent, and other feature views based on global state.',
        ],
      },
      {
        slug: 'api-client',
        title: 'frontend/src/api/client.ts',
        path: 'frontend/src/api/client.ts',
        summary: 'Typed frontend API client for calling backend endpoints from the React app.',
        details: [
          'Defines request helpers for backend paths, auth headers, and common response handling.',
          'Centralizes API URL construction and Luna key retrieval logic.',
          'Used by UI components to call chat, memory, system, agent, and Spotify endpoints.',
        ],
      },
    ],
  },
]

export function getCategoryById(id) {
  return codebaseCategories.find(category => category.id === id)
}

export function getFileBySlug(categoryId, slug) {
  const category = getCategoryById(categoryId)
  return category?.files.find(file => file.slug === slug)
}
