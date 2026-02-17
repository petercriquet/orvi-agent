import asyncio
import base64
import json
import os
import time
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from google import genai
from google.genai import types

import logging
import sys
import os
import time
from PIL import Image, ImageOps, ImageEnhance
from anticaptchaofficial.imagecaptcha import imagecaptcha

# Forzar UTF-8 en consola para Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("automaton.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Cargar variables de entorno
load_dotenv()

# Configurar Gemini
GENAI_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GENAI_API_KEY:
    logging.info("WARNING: GOOGLE_API_KEY not found in .env")

# Configurar Anti-Captcha
ANTICAPTCHA_API_KEY = os.getenv("ANTICAPTCHA_API_KEY")
if not ANTICAPTCHA_API_KEY:
    logging.error("❌ CRITICAL: ANTICAPTCHA_API_KEY not found in .env")

# Removed genai.configure, now using Client

class Oracle:
    """Maneja la validación visual usando Gemini 1.5 Flash (New SDK)."""
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.client = genai.Client(api_key=GENAI_API_KEY)
        self.model_name = model_name

    async def validate(self, screenshot_path: str, prompt: str) -> Dict[str, Any]:
        """
        Valida si el screenshot cumple con el prompt.
        Retorna un diccionario con 'passed' (bool) y 'reason' (str).
        """
        if not prompt:
            return {"passed": True, "reason": "No validation prompt provided."}

        logging.info(f"🔮 Oracle: Validando '{prompt}'...")
        
        try:
            # Leer imagen
            with open(screenshot_path, "rb") as image_file:
                image_data = image_file.read()

            # Prepare content
            # prompt_text is part of the content
            prompt_text = f"""
            Analiza esta imagen y determina si se cumple la siguiente condición: "{prompt}".
            Responde EXCLUSIVAMENTE con un JSON que tenga este formato:
            {{
                "passed": boolean,
                "reason": "breve explicación"
            }}
            """

            # Use async call via asyncio.to_thread if async client is not clear, 
            # OR use client.aio.models.generate_content if available.
            # Safe bet: wrap sync call
            
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=[
                    types.Part.from_bytes(data=image_data, mime_type="image/png"),
                    prompt_text
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            result = json.loads(response.text)
            logging.info(f"🔮 Oracle Verdict: {result.get('passed')} - {result.get('reason')}")
            return result

        except Exception as e:
            logging.info(f"❌ Oracle Error: {e}")
            return {"passed": False, "reason": f"Error interacting with Gemini: {e}"}

    async def extract_text(self, screenshot_path: str) -> str:
        """Extrae texto de una imagen (para captchas)."""
        logging.info(f"🔮 Oracle: Extrayendo texto de {screenshot_path}...")
        try:
            with open(screenshot_path, "rb") as image_file:
                image_data = image_file.read()

            prompt_text = "Analyze this image. It contains a login form with a captcha. Locate the captcha characters (alphanumeric, ignore strikethrough lines). Return ONLY the exact characters string (e.g. 'Ab3d'). No spaces, no JSON, no markdown. If the image is the form, find the captcha inside it."

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=[
                    types.Part.from_bytes(data=image_data, mime_type="image/png"),
                    prompt_text
                ]
            )
            
            text = response.text.strip()
            logging.info(f"🔮 Oracle Extracted: '{text}'")
            return text

        except Exception as e:
            logging.info(f"❌ Oracle Extraction Error: {e}")
            return ""

class CaptchaSolver:
    """Maneja la resolución de captchas usando Anti-Captcha."""
    def __init__(self):
        self.api_key = ANTICAPTCHA_API_KEY

    def solve_image(self, image_path: str) -> str:
        if not self.api_key:
            logging.error("❌ No Anti-Captcha API Key provided.")
            return ""

        logging.info(f"🧩 Sending {image_path} to Anti-Captcha...")
        solver = imagecaptcha()
        solver.set_verbose(1)
        solver.set_key(self.api_key)
        
        try:
            captcha_text = solver.solve_and_return_solution(image_path)
            if captcha_text != 0:
                logging.info(f"✅ Anti-Captcha Solved: '{captcha_text}'")
                return captcha_text
            else:
                logging.error(f"❌ Anti-Captcha Failed: {solver.error_code}")
                return ""
        except Exception as e:
            logging.error(f"❌ Anti-Captcha Exception: {e}")
            return ""

class PlaywrightEngine:
    """Maneja las interacciones con el navegador."""
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.captcha_solver = CaptchaSolver()
        self.output_dir = "screenshots"
        self.generated_files = []

    async def start(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        self.playwright = await async_playwright().start()
        # Headless=False para ver el navegador y posibles captchas
        # slow_mo=100 ralentiza cada operación de Playwright 100ms
        self.browser = await self.playwright.chromium.launch(
            channel="chrome",
            headless=False, 
            slow_mo=100,
            args=["--disable-features=Translate", "--disable-translate"]
        )
        self.context = await self.browser.new_context(
            permissions=[], # Block all permissions by default (or empty list blocks geo if not granted)
            geolocation={"latitude": 18.4861, "longitude": -69.9312} # Fake Santo Domingo just in case
        )
        # Explicitly clear permissions to be safe, or just relying on default deny.
        # Better: Grant 'geolocation' if we wanted it, but to BLOCK it, we just don't grant it. 
        # However, to dismiss the prompt, we sometimes need to explicitly grant or deny.
        # Playwright default is to PROMPT. We want to DENY or GRANT to make it go away.
        # Let's GRANT it so it doesn't pop up, but provide fake logic.
        await self.context.grant_permissions(['geolocation'], origin='https://ibp.bhd.com.do')
        
        self.page = await self.context.new_page()



    async def stop(self):
        if self.context: await self.context.close()
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()

    def _resolve_value(self, value: str) -> str:
        """Resuelve valores como 'env:VAR_NAME'."""
        if value.startswith("env:"):
            env_var = value.split(":", 1)[1]
            return os.getenv(env_var, value)
        return value

    async def get_element_screenshot(self, selector: str, filename: str):
        """Toma captura de un elemento específico."""
        try:
            element = await self.page.query_selector(selector)
            if element:
                await element.screenshot(path=filename)
                return True
            return False
        except Exception as e:
            logging.info(f"❌ Error taking element screenshot: {e}")
            return False

# ... (keep existing methods)

    async def execute_action(self, action: Dict[str, Any], oracle=None):
        """Ejecuta una acción individual de Playwright."""
        act_type = action.get("action")
        try:
            if act_type == "browse":
                url = action.get("url")
                logging.info(f"🌐 Navigating to {url}...")
                logging.info(f"🌐 Navigating to {url}...")
                await self.page.goto(url)

            elif act_type == "reload":
                logging.info("🔄 Reloading page...")
                await self.page.reload()
            
            elif act_type == "input":
                selector = action.get("element")
                value = self._resolve_value(action.get("value", ""))
                logging.info(f"⌨️ Typing into {selector}...")
                await self.page.fill(selector, value)

            elif act_type == "click":
                selector = action.get("element")
                logging.info(f"🖱️ Clicking {selector}...")
                await self.page.click(selector)
            
            elif act_type == "wait":
                duration = action.get("duration", 2000)
                logging.info(f"⏳ Waiting {duration}ms...")
                await self.page.wait_for_timeout(duration)

            elif act_type == "solve_captcha":
                img_selector = action.get("image_element")
                input_selector = action.get("input_element")
                
                logging.info(f"🧩 Solving Captcha (Image: {img_selector})...")
                
                # Take screenshot of captcha (Save with timestamp for debugging)
                # Take screenshot of captcha (Save with timestamp for debugging)
                timestamp = int(time.time())
                captcha_filename = f"captcha_{timestamp}.png"
                processed_filename = f"captcha_{timestamp}_clean.png"
                
                captcha_file = os.path.join(self.output_dir, captcha_filename)
                processed_file = os.path.join(self.output_dir, processed_filename)
                
                if await self.get_element_screenshot(img_selector, captcha_file):
                    logging.info(f"   📸 Captcha image saved to {captcha_file}")
                    self.generated_files.append(captcha_file)
                    
                    # Preprocess Image
                    if self.process_image(captcha_file, processed_file):
                        target_file = processed_file
                        self.generated_files.append(processed_file)
                    else:
                        target_file = captcha_file

                    # Use Anti-Captcha
                    # Run in thread to avoid blocking loop (Anti-Captcha is sync)
                    captcha_text = await asyncio.to_thread(self.captcha_solver.solve_image, target_file)
                    
                    if captcha_text:
                         await self.page.fill(input_selector, captcha_text)
                    else:
                        logging.error("⚠️ Failed to solve captcha (Text is empty/0). Raising exception to trigger retry.")
                        raise Exception("Captcha Solve Failed")
                else:
                    logging.info(f"⚠️ Captcha image element not found: {img_selector}")

            else:
                logging.info(f"⚠️ Unknown action: {act_type}")

        except Exception as e:
            if action.get("optional"):
                logging.info(f"⚠️ Optional action '{act_type}' failed or skipped: {e}. Continuing...")
            else:
                logging.info(f"❌ Action Error ({act_type}): {e}")
                raise e

    async def take_screenshot(self, filename: str):
        await self.page.screenshot(path=filename)
    
    def process_image(self, input_path: str, output_path: str):
        """Pre-procesa la imagen para limpiar ruido."""
        try:
            img = Image.open(input_path).convert("L") # Grayscale
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)
            img = img.point(lambda p: p > 150 and 255) 
            img.save(output_path)
            logging.info(f"   🖼️ Image processed and saved to {output_path}")
            return True
        except Exception as e:
            logging.info(f"❌ Error processing image: {e}")
            return False

class SmartRetryLoop:
    """Maneja el bucle de intentos y validación."""
    def __init__(self, mission_file: str):
        self.mission_file = mission_file
        self.engine = PlaywrightEngine()
        self.oracle = Oracle()
        self.max_retries = 3
        self.generated_files = [] # Track validation screenshots

    def load_mission(self) -> List[List[Dict]]:
        with open(self.mission_file, "r") as f:
            return json.load(f)

    async def run(self):
        mission_steps = self.load_mission()
        await self.engine.start()

        try:
            for step_index, step_actions in enumerate(mission_steps):
                logging.info(f"\n🚀 Starting Step {step_index + 1}...")
                
                success = False
                attempts = 0

                while not success and attempts < self.max_retries:
                    attempts += 1
                    logging.info(f"   Attempt {attempts}/{self.max_retries}")

                    try:
                        # 1. Ejecutar Acciones
                        for action in step_actions:
                            await self.engine.execute_action(action, oracle=self.oracle)

                        # 2. Pausa de Estabilización
                        logging.info("   Waiting for stabilization (2s)...")
                        await asyncio.sleep(2)

                        # 3. Validación Visual
                        validation_prompt = next((a.get("prompt_ia") for a in step_actions if "prompt_ia" in a), None)

                        if validation_prompt:
                            # Validation Polling Loop
                            last_action = step_actions[-1]
                            val_settings = last_action.get("validation_settings", {})
                            
                            max_val_attempts = val_settings.get("polling_attempts", 3)
                            polling_delay = val_settings.get("polling_delay", 5)
                            
                            val_attempt = 0
                            
                            while val_attempt < max_val_attempts and not success:
                                val_attempt += 1
                                if val_attempt > 1:
                                    logging.info(f"   ⏳ Polling validation ({val_attempt}/{max_val_attempts})... waiting {polling_delay}s")
                                    await asyncio.sleep(polling_delay)

                                    logging.info(f"   ⏳ Polling validation ({val_attempt}/{max_val_attempts})... waiting {polling_delay}s")
                                    await asyncio.sleep(polling_delay)

                                screenshot_filename = f"step_{step_index}_attempt_{attempts}_val_{val_attempt}.png"
                                screenshot_path = os.path.join(self.engine.output_dir, screenshot_filename)
                                
                                await self.engine.take_screenshot(screenshot_path)
                                self.generated_files.append(screenshot_path)
                                
                                verdict = await self.oracle.validate(screenshot_path, validation_prompt)
                                
                                if verdict.get("passed"):
                                    logging.info("✅ Validation Passed!")
                                    success = True
                                else:
                                    logging.info(f"🛑 Validation Failed: {verdict.get('reason')}")
                            
                            if not success and attempts < self.max_retries:
                                logging.info("   ⚠️ Step failed after validation polling. Retrying actions in 5s...")
                                await asyncio.sleep(5)
                        else:
                            logging.info("ℹ️ No validation prompt for this step. Assuming success.")
                            success = True

                    except Exception as e:
                        logging.info(f"❌ Error in step execution: {e}")
                        if attempts < self.max_retries:
                            await asyncio.sleep(5)

                if not success:
                    logging.info(f"💀 CRITICAL FAILURE: Step {step_index + 1} failed after {self.max_retries} attempts.")
                    break
        
        finally:
            await self.engine.stop()
            
            # Cleanup Logic
            all_files = self.engine.generated_files + self.generated_files
            if success:
                logging.info("🧹 Mission Successful! Cleaning up intermediate files...")
                # Keep only the last generated file (assuming it's the success proof)
                if all_files:
                    last_file = all_files[-1]
                    for f in all_files:
                        if f != last_file and os.path.exists(f):
                            try:
                                os.remove(f)
                                logging.info(f"   Deleted {f}")
                            except Exception as e:
                                logging.error(f"   Failed to delete {f}: {e}")
                    logging.info(f"✨ Kept final proof: {last_file}")
            else:
                logging.info("📝 Mission Failed. Keeping all screenshots for debugging.")

            logging.info("🏁 Mission Cycle Ended.")


import sys

async def main():
    mission_file = sys.argv[1] if len(sys.argv) > 1 else "mission.json"
    automaton = SmartRetryLoop(mission_file)
    await automaton.run()

if __name__ == "__main__":
    asyncio.run(main())
