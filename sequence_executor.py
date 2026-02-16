import asyncio
import json
import os
import time
import logging
import uuid
import datetime
import traceback
from dotenv import load_dotenv
from automaton import PlaywrightEngine

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load Environment
load_dotenv()

class SequenceExecutor:
    def __init__(self):
        self.logs = []
        self.screenshots_dir = os.path.join(os.getcwd(), "screenshots")
        if not os.path.exists(self.screenshots_dir):
            os.makedirs(self.screenshots_dir)

    def log(self, message: str, level: str = "INFO"):
        """Logs a message to the internal list and standard logger."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] {level}: {message}"
        self.logs.append(formatted_message)
        if level == "ERROR":
            logging.error(message)
        else:
            logging.info(message)

    def resolve_data(self, data):
        """
        Resolves a data string that might contain environment variable references.
        """
        if data and isinstance(data, str) and data.startswith("env:"):
            env_key = data.split("env:")[1]
            return os.getenv(env_key, "")
        return data

    async def process_steps(self, engine: PlaywrightEngine, steps: list, coordinates: dict):
        """
        Iterates through a list of steps and executes them.
        """
        for step in steps:
            action = step.get("action")
            element = step.get("element")
            data = self.resolve_data(step.get("data"))
            wait_after = step.get("wait_after", 1)
            optional = step.get("optional", False)
            
            self.log(f"➡️ Executing Step: {action} on {element or 'N/A'} (Optional: {optional})")
            
            try:
                if action == "navigate":
                    current_url = engine.page.url.rstrip('/')
                    target_url = data.rstrip('/')
                    
                    if current_url == target_url:
                        self.log(f"   🔄 Already on {target_url}. Forcing RELOAD to reset state...")
                        await engine.page.reload(wait_until="domcontentloaded")
                    else:
                        await engine.page.goto(data, wait_until="domcontentloaded")
                    
                elif action == "input":
                    await engine.page.wait_for_selector(element, state="visible", timeout=5000)
                    await engine.page.click(element)
                    await engine.page.keyboard.press("Control+A")
                    await engine.page.keyboard.press("Backspace")
                    await engine.page.keyboard.type(data, delay=50)
                        
                elif action == "click":
                    timeout = 2000 if optional else 5000
                    await engine.page.wait_for_selector(element, state="visible", timeout=timeout)
                    await engine.page.click(element)
                    
                elif action == "captcha":
                    captcha_visible = await engine.page.is_visible(data)
                    
                    if captcha_visible:
                        self.log(f"   🧩 Captcha detected ({data}). Solving...")
                        captcha_action = {
                            "action": "solve_captcha",
                            "image_element": data,
                            "input_element": element
                        }
                        await engine.execute_action(captcha_action)
                    else:
                        self.log(f"   ℹ️ Captcha NOT detected ({data}). Skipping step.")
                    
                elif action == "wait":
                    pass
                    
                elif action == "dynamic_input":
                    lookup_source = step.get("lookup_source", "coordinates.json") # Just for reference in logs if needed, but we use passed coordinates
                    read_selector = data
                    write_selector = element

                    # 1. Read key from page
                    await engine.page.wait_for_selector(read_selector, state="visible", timeout=5000)
                    raw_text = await engine.page.inner_text(read_selector)
                    key = raw_text.strip().replace("0", "") if raw_text.startswith("0") and len(raw_text) == 2 else raw_text.strip()
                    
                    self.log(f"   🔑 Challenge Key Detected: '{key}' (Raw: '{raw_text}')")

                    # 2. Lookup Value from provided coordinates
                    value = coordinates.get(key)
                    if value:
                        self.log(f"   ✅ Value Found: {value}")
                        # 3. Write Value
                        await engine.page.wait_for_selector(write_selector, state="visible", timeout=5000)
                        await engine.page.fill(write_selector, value)
                    else:
                         raise Exception(f"Key '{key}' not found in provided coordinates")

                # Handle post-step wait
                if wait_after > 0:
                    self.log(f"   ⏳ Waiting {wait_after}s...")
                    await asyncio.sleep(wait_after)

            except Exception as e:
                if optional:
                    self.log(f"   ⚠️ Optional step failed/skipped: {e}. Continuing...")
                else:
                    self.log(f"❌ Error in step {action}: {e}", "ERROR")
                    raise e

    async def process_sequence(self, engine: PlaywrightEngine, sequence: dict, coordinates: dict):
        """Processes a single sequence with retries."""
        title = sequence.get("title")
        intents = sequence.get("intents_number", 1)
        target = sequence.get("target_element")
        target_wait = sequence.get("target_element_wait", 0)
        steps = sequence.get("steps", [])
        
        self.log(f"🎬 SELECTING SEQUENCE: {title} (Max Intents: {intents})")
        
        for attempt in range(1, intents + 1):
            self.log(f"   🔄 Attempt {attempt}/{intents}")
            try:
                await self.process_steps(engine, steps, coordinates)
                
                if target:
                    self.log(f"   🎯 Waiting up to {int(target_wait)}s for target '{target}'...")
                    try:
                        await engine.page.wait_for_selector(target, state="visible", timeout=int(target_wait * 1000))
                        self.log(f"   ✅ SUCCESS: Target '{target}' found.")
                        return True
                    except Exception:
                        self.log(f"   ⚠️ FAILURE: Target '{target}' NOT found after attempt {attempt}.", "WARNING")
                else:
                    self.log("   ✅ SUCCESS: Sequence completed (no target defined).")
                    return True
                    
            except Exception as e:
                self.log(f"   ❌ EXCEPTION: {e}", "ERROR")
                
            if attempt < intents:
                self.log("   ♻️ Retrying...")
                await asyncio.sleep(2)
                
        self.log(f"🛑 SEQUENCE FAILED: {title} failed after {intents} attempts.", "ERROR")
        return False

    async def execute(self, sequences: list, coordinates: dict):
        """
        Executes the list of sequences.
        Returns a dictionary with result, logs, and screenshot filename.
        """
        self.logs = [] # Reset logs
        engine = PlaywrightEngine()
        success = True
        
        try:
            await engine.start()
            start_time = time.time()
            
            for seq in sequences:
                seq_success = await self.process_sequence(engine, seq, coordinates)
                if not seq_success:
                    self.log("💀 FLOW ABORTED: Critical sequence failed.", "ERROR")
                    success = False
                    break
            
            end_time = time.time()
            duration = end_time - start_time
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            self.log(f"🎉 FLOW FINISHED IN: {minutes}m {seconds}s")
            
        except Exception as e:
            self.log(f"🔥 CRITICAL UNHANDLED ERROR: {e}\n{traceback.format_exc()}", "ERROR")
            success = False
        finally:
            # Capture Screenshot
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = uuid.uuid4()
            screenshot_filename = f"execution_{timestamp}_{unique_id}.png"
            screenshot_path = os.path.join(self.screenshots_dir, screenshot_filename)
            
            try:
                await engine.page.screenshot(path=screenshot_path)
                self.log(f"📸 Screenshot saved: {screenshot_filename}")
            except Exception as e:
                self.log(f"❌ Failed to take screenshot: {e}", "ERROR")
                screenshot_filename = None # Indicator of failure to screenshot

            try:
                await engine.stop()
            except Exception as e:
                self.log(f"⚠️ Error stopping engine (likely already closed): {e}", "WARNING")

        return {
            "success": success,
            "logs": self.logs,
            "screenshot": screenshot_filename
        }

async def main():
    # 1. Load Sequences
    with open("sequences.json", "r", encoding="utf-8") as f:
        sequences = json.load(f)
    
    # Load coordinates (mocking what would be passed via API, but reading from file for standalone)
    with open("coordinates.json", "r", encoding="utf-8") as f:
        coordinates = json.load(f)
        
    executor = SequenceExecutor()
    result = await executor.execute(sequences, coordinates)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
