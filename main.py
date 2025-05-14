import logging
import json
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv
import traceback
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# Initialize FastAPI with Saksoft HR Agent metadata
app = FastAPI(
    title="Saksoft HR Agent API",
    description="A FastAPI application for interacting with the Saksoft HR Agent. "
                "This API allows authorized users to send messages to an HR agent "
                "via secure endpoints, using Bearer token authentication and "
                "integrating with an external HR agent service. Supports both "
                "chat and streaming interactions.",
    version="1.0.0"
)
security = HTTPBearer()

class ChatRequest(BaseModel):
    session_id: str
    message: str

class StreamRequest(BaseModel):
    session_id: str
    message: str

async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    logger.debug("Verifying Bearer token")
    expected_token = os.getenv("BEARER_TOKEN")
    if credentials.credentials != expected_token:
        logger.error("Invalid Bearer token provided")
        raise HTTPException(status_code=401, detail="Invalid or missing Bearer token")
    logger.debug("Bearer token verified successfully")
    return credentials.credentials

@app.post("/chat", tags=["HR Agent"])
async def chat_with_agent(request: ChatRequest, token: str = Depends(verify_token)):
    logger.info(f"Received chat request with session_id: {request.session_id}, message: {request.message}")
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "Content-Type": "application/json",
                "x-api-key": os.getenv("API_KEY")
            }
            
            payload = {
                "user_id": os.getenv("USER_ID", "default_user"),
                "agent_id": os.getenv("AGENT_ID", ""),
                "session_id": request.session_id,
                "message": request.message,
                "system_prompt_variables": {},
                "filter_variables": {},
                "features": []
            }
            
            logger.debug(f"Sending request to {os.getenv('AGENT_API_URL')} with payload: {payload}")
            response = await client.post(
                os.getenv("AGENT_API_URL"),
                json=payload,
                headers=headers
            )
            
            logger.debug(f"Received response with status: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            if "response" not in result:
                logger.error("Response field missing in API response")
                raise HTTPException(status_code=500, detail="Invalid response format from HR agent API")
            logger.info("Successfully processed chat request")
            return {"response": result["response"]}
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {str(e)}, status: {e.response.status_code}, detail: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

async def stream_response(client: httpx.AsyncClient, url: str, headers: Dict[str, str], payload: Dict[str, Any]):
    async with client.stream("POST", url, json=payload, headers=headers) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if line:
                try:
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]
                    else:
                        logger.debug(f"Streamed chunk without response field: {data}")
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in streamed chunk: {line}")
                    continue

# @app.post("/stream", , tags=["HR Agent"])
# async def stream_with_agent(request: StreamRequest, token: str = Depends(verify_token)):
#     logger.info(f"Received stream request with session_id: {request.session_id}, message: {request.message}")
#     try:
#         headers = {
#             "Content-Type": "application/json",
#             "x-api-key": os.getenv("API_KEY")
#         }
        
#         payload = {
#             "user_id": os.getenv("USER_ID", "default_user"),
#             "agent_id": os.getenv("AGENT_ID", ""),
#             "session_id": request.session_id,
#             "message": request.message,
#             "system_prompt_variables": {},
#             "filter_variables": {},
#             "features": []
#         }
        
#         stream_url = os.getenv("AGENT_STREAM_API_URL")
#         if not stream_url:
#             logger.error("AGENT_STREAM_API_URL not set in environment variables")
#             raise HTTPException(status_code=500, detail="Streaming API URL not configured")
#         logger.debug(f"Sending streaming request to {stream_url} with payload: {payload}")
        
#         async with httpx.AsyncClient(timeout=30.0) as client:
#             return StreamingResponse(
#                 stream_response(client, stream_url, headers, payload),
#                 media_type="text/event-stream"
#             )
            
#     except httpx.HTTPStatusError as e:
#         logger.error(f"HTTP error occurred: {str(e)}, status: {e.response.status_code}, detail: {e.response.text}")
#         raise HTTPException(status_code=e.response.status_code, detail=str(e))
#     except Exception as e:
#         logger.error(f"Unexpected error occurred: {str(e)}")
#         logger.debug(f"Traceback: {traceback.format_exc()}")
#         raise HTTPException(status_code=500, detail=str(e))


# Health Check
@app.get("/health", tags=["System"])
def health_check():
    return {"status": "healthy"}