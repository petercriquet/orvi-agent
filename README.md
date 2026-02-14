# Orvi-Agent: Automating BHD Banking Transfers 🤖💸

This project implements a deterministic, sequence-based automation agent for the BHD bank web portal. It handles login (with captcha solving), navigation, and fund transfers using a JSON-configured engine.

## 🚀 Features

- **Deterministic Execution**: Driven by `sequences.json`, ensuring predictable and repeatable steps.
- **Smart Waits**: Uses dynamic element waiting instead of hard sleeps for maximum speed.
- **Captcha Solving**: Integrates with Anti-Captcha service to bypass login challenges.
- **Dynamic Token Handling**: Reads coordinate challenges (e.g., "H3") and inputs the correct value from a secure lookup file.
- **Resilient**: Handles page reloads, unexpected modals, and retries failed steps automatically.

## 📂 Project Structure

- `sequence_executor.py`: The main engine. Reads sequences and executes them using Playwright.
- `sequences.json`: Configuration file defining the automation flow (Login -> Navigate -> Transfer).
- `automaton.py`: Core Playwright wrapper and browser management.
- `coordinates.json`: **(SENSITIVE)** Key-value map for the physical coordinate card.
- `.env`: **(SENSITIVE)** Environment variables for credentials.

## 🛠️ Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    playwright install chromium
    ```

2.  **Configure Environment (`.env`)**:
    ```ini
    BHD_USER=your_user
    BHD_PASS=your_password
    ANTICAPTCHA_API_KEY=your_key
    ```

3.  **Configure Coordinates (`coordinates.json`)**:
    Create a JSON file mapping your card's codes to values:
    ```json
    {
      "1": "1234",
      "2": "5678",
      ...
    }
    ```

## 🏃 Usage

Run the agent:
```bash
python sequence_executor.py
```

## ⚙️ Configuration (`sequences.json`)

You can modify steps in `sequences.json` to adjust timeouts, selectors, or data.
- **`target_element`**: The selector to wait for to confirm sequence success.
- **`dynamic_input`**: Special action to handle dynamic challenges.

## ⚠️ Disclaimer

This tool is for educational and personal automation purposes. Use responsibly and ensure your credentials are secure.
