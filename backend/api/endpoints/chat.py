from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse # For streaming chat later
from sqlalchemy.orm import Session
import logging
import uuid # For generating session IDs

# Import schemas, db session dependency, and agent function
from backend import schemas # Assuming schemas.py is in backend/
from backend.database import get_db
from backend.agent import get_agent_response # Import the actual agent function

router = APIRouter()
logger = logging.getLogger(__name__)

# Restore response_model (using the simplified ChatResponse for now)
@router.post("", response_model=schemas.ChatResponse)
# @router.post("")
async def handle_chat(
    request: schemas.ChatRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Handles incoming chat messages, invokes the agent, and returns the response.
    Generates a session_id if one is not provided.
    # (NOTE: response_model commented out for debugging 422 error)
    """
    # Restore session ID generation
    session_id = request.session_id or str(uuid.uuid4())
    logger.info(f"Received chat request from user {request.user_id} (session: {session_id})")
    # logger.info(f"Received chat request from user {request.user_id}") # Log without session
    logger.info(f"Message: {request.message}")

    # --- Call the Agent --- #
    try:
        # Pass session_id and db again
        response = await get_agent_response(
            user_id=request.user_id,
            message=request.message,
            session_id=session_id,
            db=db
        )
    except Exception as e:
        logger.error(f"Error calling agent for session {session_id}: {e}", exc_info=True)
        # logger.error(f"Error calling agent for user {request.user_id}: {e}", exc_info=True) # Log without session
        raise HTTPException(status_code=500, detail="Internal server error processing chat message.")
    # -------------------- #

    # --- Streaming Response (Future Implementation) ---
    # Remains the same for now
    # async def stream_generator():
    #     async for chunk in get_agent_response_stream(...):
    #         yield f"data: {json.dumps(chunk)}\n\n"
    # return StreamingResponse(stream_generator(), media_type="text/event-stream")
    # ----------------------------------------------- #

    logger.info(f"Sending agent reply to user {request.user_id} (session: {session_id})")
    # logger.info(f"Sending agent reply to user {request.user_id}") # Log without session
    return response 