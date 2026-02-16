from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from sequence_executor import SequenceExecutor
import logging
import sys
import asyncio

# Enforce ProactorEventLoop on Windows for Playwright
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Initialize FastAPI app
app = FastAPI(title="Orvi-Agent Sequence Executor API", version="1.0.0")

# --- Data Models ---

class StepModel(BaseModel):
    """
    Represents a single step in a sequence.
    """
    action: str
    element: Optional[str] = None
    data: Optional[str] = None
    wait_after: int = 1
    optional: bool = False
    lookup_source: Optional[str] = None

class SequenceModel(BaseModel):
    """
    Represents a sequence of actions to perform.
    """
    title: str
    intents_number: int = 1
    target_element: Optional[str] = None
    target_element_wait: int = 0
    steps: List[StepModel]

class ExecutionRequest(BaseModel):
    """
    The payload expected by the /execute endpoint.
    """
    sequences: List[SequenceModel]
    coordinates: Dict[str, str]

class ExecutionResponse(BaseModel):
    """
    The response returned by the /execute endpoint.
    """
    success: bool
    screenshot: Optional[str]
    logs: List[str]

# --- Endpoints ---

@app.post("/execute", response_model=ExecutionResponse)
async def execute_sequence(request: ExecutionRequest):
    """
    Executes a list of sequences provided in the payload.
    Returns the execution result, logs, and a screenshot filename.
    """
    logging.info(f"🚀 Received execution request with {len(request.sequences)} sequences.")
    
    executor = SequenceExecutor()
    
    # Convert Pydantic models to list of dicts/dicts expected by Executor
    # The models are compatible, but we can dump them to dicts to be safe 
    # and consistent with existing logic.
    sequences_data = [seq.model_dump() for seq in request.sequences]
    coordinates_data = request.coordinates
    
    try:
        result = await executor.execute(sequences_data, coordinates_data)
        return ExecutionResponse(**result)
    except Exception as e:
        error_msg = f"🔥 API CRITICAL ERROR: {str(e)}"
        logging.error(error_msg)
        return ExecutionResponse(
            success=False,
            logs=[error_msg],
            screenshot=None
        )

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_running_loop()
    logging.info(f"🚀 API Startup. Event Loop: {type(loop)}")
    if sys.platform == "win32" and not isinstance(loop, asyncio.ProactorEventLoop):
        logging.warning("⚠️ WARNING: Not running on ProactorEventLoop! Playwright may fail.")

@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Orvi-Agent Sequence Executor API")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the API on")
    args = parser.parse_args()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    uvicorn.run(app, host="0.0.0.0", port=args.port)
