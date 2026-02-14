import asyncio
import json
import os
import time
import logging
from dotenv import load_dotenv
from automaton import PlaywrightEngine

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load Environment
load_dotenv()

def resolve_data(data):
    """
    Resolves a data string that might contain environment variable references.
    
    Args:
        data (str): The string to resolve. e.g., "env:BHD_USER" or "100".
        
    Returns:
        str: The resolved value from OS environment or the original string.
    """
    if data and isinstance(data, str) and data.startswith("env:"):
        env_key = data.split("env:")[1]
        return os.getenv(env_key, "")
    return data

async def process_steps(engine: PlaywrightEngine, steps: list):
    """
    Iterates through a list of steps and executes them using the PlaywrightEngine.
    
    Handles:
    - strict element waiting
    - optional steps (warnings instead of errors)
    - dynamic inputs (coordinate cards)
    - captcha solving
    
    Args:
        engine (PlaywrightEngine): The active browser engine instance.
        steps (list): A list of dictionary objects defining the actions.
    """
    for step in steps:
        action = step.get("action")
        element = step.get("element")
        data = resolve_data(step.get("data"))
        wait_after = step.get("wait_after", 1)
        optional = step.get("optional", False)
        
        logging.info(f"➡️ Executing Step: {action} on {element or 'N/A'} (Optional: {optional})")
        
        try:
            if action == "navigate":
                # FORCE RELOAD: If already on the page, reload to reset captcha
                # Normalize URLs (strip trailing slashes)
                current_url = engine.page.url.rstrip('/')
                target_url = data.rstrip('/')
                
                if current_url == target_url:
                    logging.info(f"   🔄 Already on {target_url}. Forcing RELOAD to reset state...")
                    await engine.page.reload(wait_until="domcontentloaded")
                else:
                    await engine.page.goto(data, wait_until="domcontentloaded")
                
            elif action == "input":
                # STRICT: Wait for element to be visible
                await engine.page.wait_for_selector(element, state="visible", timeout=5000)
                await engine.page.click(element)
                await engine.page.keyboard.press("Control+A")
                await engine.page.keyboard.press("Backspace")
                await engine.page.keyboard.type(data, delay=50)
                    
            elif action == "click":
                # Wait for element (shorter timeout for optional steps)
                timeout = 2000 if optional else 5000
                await engine.page.wait_for_selector(element, state="visible", timeout=timeout)
                await engine.page.click(element)
                
            elif action == "captcha":
                # CONDITIONAL: Only solve if captcha image is visible
                # Quick check (1s timeout) to see if captcha exists
                captcha_visible = await engine.page.is_visible(data)
                
                if captcha_visible:
                    logging.info(f"   🧩 Captcha detected ({data}). Solving...")
                    # Uses automaton's solve_captcha logic
                    captcha_action = {
                        "action": "solve_captcha",
                        "image_element": data, # In JSON 'data' is the image selector
                        "input_element": element # In JSON 'element' is the input selector
                    }
                    await engine.execute_action(captcha_action)
                else:
                    logging.info(f"   ℹ️ Captcha NOT detected ({data}). Skipping step.")
                
            elif action == "wait":
                # Explicit wait logic if needed, usually wait_after handles it
                pass
                
            elif action == "dynamic_input":
                # Logic: Read key from 'data' (element selector), lookup validation in coordinates.json, write to 'element'
                lookup_source = step.get("lookup_source", "coordinates.json")
                read_selector = data  # In JSON, 'data' holds the selector to READ from
                write_selector = element # In JSON, 'element' holds the selector into INPUT

                # 1. Read key from page
                await engine.page.wait_for_selector(read_selector, state="visible", timeout=5000)
                raw_text = await engine.page.inner_text(read_selector)
                key = raw_text.strip().replace("0", "") if raw_text.startswith("0") and len(raw_text) == 2 else raw_text.strip()
                # Also handle cases like " 01 " -> "1"
                
                logging.info(f"   🔑 Challenge Key Detected: '{key}' (Raw: '{raw_text}')")

                # 2. Lookup Value
                if os.path.exists(lookup_source):
                    with open(lookup_source, "r") as f:
                        coords = json.load(f)
                    
                    value = coords.get(key)
                    if value:
                        logging.info(f"   ✅ Value Found: {value}")
                        # 3. Write Value
                        await engine.page.wait_for_selector(write_selector, state="visible", timeout=5000)
                        await engine.page.fill(write_selector, value)
                    else:
                         raise Exception(f"Key '{key}' not found in {lookup_source}")
                else:
                    raise Exception(f"Lookup file {lookup_source} not found.")

            # Handle post-step wait
            if wait_after > 0:
                logging.info(f"   ⏳ Waiting {wait_after}s...")
                await asyncio.sleep(wait_after)

        except Exception as e:
            if optional:
                logging.info(f"   ⚠️ Optional step failed/skipped: {e}. Continuing...")
            else:
                logging.error(f"❌ Error in step {action}: {e}")
                raise e # Fail the sequence to trigger retry logic

async def process_sequence(engine: PlaywrightEngine, sequence: dict):
    """Processes a single sequence with retries."""
    title = sequence.get("title")
    intents = sequence.get("intents_number", 1)
    target = sequence.get("target_element")
    target_wait = sequence.get("target_element_wait", 0)
    steps = sequence.get("steps", [])
    
    logging.info(f"🎬 SELECTING SEQUENCE: {title} (Max Intents: {intents})")
    
    for attempt in range(1, intents + 1):
        logging.info(f"   🔄 Attempt {attempt}/{intents}")
        try:
            await process_steps(engine, steps)
            
            # Post-sequence wait: Replaced by target check wait
            
            # Check Target
            if target:
                logging.info(f"   🎯 Waiting up to {int(target_wait)}s for target '{target}'...")
                try:
                    await engine.page.wait_for_selector(target, state="visible", timeout=int(target_wait * 1000))
                    logging.info(f"   ✅ SUCCESS: Target '{target}' found.")
                    return True
                except Exception:
                    logging.warning(f"   ⚠️ FAILURE: Target '{target}' NOT found after attempt {attempt}.")
            else:
                logging.info("   ✅ SUCCESS: Sequence completed (no target defined).")
                return True

                
        except Exception as e:
            logging.error(f"   ❌ EXCEPTION: {e}")
            
        # If we failed specific target check or caught exception, we loop again
        if attempt < intents:
            logging.info("   ♻️ Retrying...")
            await asyncio.sleep(2) # Cooldown
            
    logging.error(f"🛑 SEQUENCE FAILED: {title} failed after {intents} attempts.")
    return False

async def main():
    # 1. Load Sequences
    with open("sequences.json", "r", encoding="utf-8") as f:
        sequences = json.load(f)
        
    # 2. Initialize Engine
    engine = PlaywrightEngine()
    await engine.start()
    
    try:
        # Start Timer
        start_time = time.time()
        
        # 3. Process Flow
        for seq in sequences:
            success = await process_sequence(engine, seq)
            if not success:
                logging.error("💀 FLOW ABORTED: Critical sequence failed.")
                break
        
        end_time = time.time()
        duration = end_time - start_time
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        
        logging.info(f"🎉 FLOW FINISHED IN: {minutes}m {seconds}s")
        
    finally:
        await engine.stop()

if __name__ == "__main__":
    asyncio.run(main())
