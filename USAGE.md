# Orvi-Agent API Usage Guide

This guide explains how to use the Sequence Executor API, both as a Python script and as a standalone executable.

## 1. Running the API

### Option A: Using Python (Development)
Ensure dependencies are installed (`pip install -r requirements.txt`).
```bash
python api.py --port 8000
```

### Option B: Using Standalone Executable (Production)
Run the executable directly. It must be in the same folder as `sequences.json` and `coordinates.json`.
```cmd
OrviAgentAPI.exe --port 8080
```

## 2. API Endpoint

-   **URL**: `POST http://localhost:<port>/execute`
-   **Content-Type**: `application/json`

### Payload Example
```json
{
  "sequences": [
    {
      "title": "Login",
      "steps": [
        {"action": "navigate", "data": "https://example.com"},
        {"action": "input", "element": "#user", "data": "myuser"},
        {"action": "click", "element": "#login"}
      ]
    }
  ],
  "coordinates": {
    "01": "1234",
    "02": "5678"
  }
}
```

### Response Example
```json
{
  "success": true,
  "screenshot": "execution_20231027_120000_uuid.png",
  "logs": [
    "[INFO] Navigating...",
    "[INFO] Clicking..."
  ]
}
```

## 3. Notes
-   **Screenshots**: Saved in the `screenshots/` folder relative to the executable/script.
-   **Browser**: Uses the system's installed Google Chrome.
