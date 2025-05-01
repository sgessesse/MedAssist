import logging
import json
import os
from typing import Optional, List, Dict, Any, Generator

from sqlalchemy.orm import Session
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import Tool, tool # Use @tool decorator for simpler tool definition
from langchain.memory import ConversationBufferMemory # Restore Memory
# from langchain_community.chat_message_histories import RedisChatMessageHistory # Example for persistent memory
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.history import RunnableWithMessageHistory # Restore History
from pydantic import BaseModel, Field as PydanticField # Avoid conflict with langchain Field
from langchain_core.utils.function_calling import format_tool_to_openai_tool
import dateparser # Import dateparser
from langchain_core.messages import SystemMessage # Import SystemMessage
from langchain_core.agents import AgentAction, AgentFinish # Import message types
import re # Import regex module
from datetime import datetime # Import datetime

from backend import schemas, crud # Import crud
from backend.core.config import settings # Import centralized settings
from backend.database import SessionLocal # Import SessionLocal
# Import crud later when needed for DB tools
# from backend import crud

# Get a logger instance specific to this module
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s') # Remove this line
logger = logging.getLogger(__name__)

# --- Global Agent Components (Initialize once) --- #
# We initialize these outside the request function for efficiency.
# Ensure API keys and paths are valid before starting the API.

llm = None
embeddings = None
vectorstore = None
retriever = None
symptom_rules = None
agent_executor_with_history = None # Restore this

# Restore memory components
session_memory_store = {}

# --- Add Custom Callback Handler --- #
from langchain.callbacks.base import BaseCallbackHandler
from typing import Dict, Any, List, Optional, Union
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.outputs import LLMResult

# Simple in-memory store for captured tags (could be improved for scaling)
_captured_triage_tags: Dict[str, str] = {}

class TriageTagCaptureHandler(BaseCallbackHandler):
    """A custom callback handler to capture the triage tag from tool output."""

    def __init__(self, session_id: str):
        super().__init__()
        self.session_id = session_id
        # Clear any previous tag for this session on initialization
        if self.session_id in _captured_triage_tags:
            del _captured_triage_tags[self.session_id]

    def on_tool_end(
        self, output: str, *, tool_name: str = "triage_symptoms", **kwargs: Any
    ) -> None:
        """Capture the triage tag when the triage_symptoms tool ends."""
        # Note: The output here is often the *string representation* of the tool's return value.
        # We rely on the verbose logging still printing the actual dictionary.
        # A more robust way would be to ensure the tool output is always JSON parseable.
        # For now, let's parse the string representation heuristically.
        # logger.debug(f"[Callback] Tool '{tool_name}' ended. Raw output string: {output}") # Keep debug if needed
        if tool_name == "triage_symptoms":
            try:
                # Attempt to parse the JSON string output from the tool
                observation = json.loads(output)
                if isinstance(observation, dict):
                    triage_value = observation.get("triage")
                    if triage_value:
                        tag = str(triage_value)
                        _captured_triage_tags[self.session_id] = tag
                        logger.info(f"[Callback] Captured triage tag '{tag}' for session {self.session_id}")
            except Exception as e:
                logger.warning(f"[Callback] Failed to parse triage tool output string '{output}': {e}")

    # Implement other methods like on_agent_action, on_llm_end etc. if needed for more complex logic
    # def on_agent_action(self, action: AgentAction, **kwargs: Any) -> Any: ...
    # def on_llm_end(self, response: LLMResult, **kwargs: Any) -> Any: ...

    @staticmethod
    def get_captured_tag(session_id: str) -> Optional[str]:
        """Retrieve the captured tag for a session."""
        return _captured_triage_tags.pop(session_id, None) # Pop to clear after retrieval
# --------------------------------- #

def get_session_history(session_id: str):
    """Gets the chat message history for a given session_id."""
    if session_id not in session_memory_store:
        # Create the full memory object, which includes the chat history
        session_memory_store[session_id] = ConversationBufferMemory(
            memory_key="chat_history", return_messages=True
        )
    # Return the underlying ChatMessageHistory object stored within the memory
    return session_memory_store[session_id].chat_memory

def initialize_agent_components():
    """Initializes LLM, embeddings, vector store, and rules."""
    global llm, embeddings, vectorstore, retriever, symptom_rules, agent_executor_with_history # Use history executor
    logger.info("Initializing agent components...")

    # Check for Google API Key early
    if not settings.google_api_key:
        logger.error("GOOGLE_API_KEY not set in environment variables.")
        raise ValueError("GOOGLE_API_KEY is required.")

    # --- Initialize LLM & Embeddings ---
    try:
        logger.info(f"Initializing LLM: {settings.llm_model_name}")
        llm = ChatGoogleGenerativeAI(
            model=settings.llm_model_name,
            google_api_key=settings.google_api_key,
            temperature=settings.agent_temperature,
            max_output_tokens=settings.agent_max_tokens,
        )
        logger.info(f"Initializing Embeddings: {settings.embedding_model_name}")
        embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model_name, google_api_key=settings.google_api_key
        )
        logger.info("LLM and Embeddings initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing Google components: {e}")
        raise

    # --- Initialize Vector Store (ChromaDB) ---
    if not settings.chroma_persist_dir.exists():
        logger.error(f"ChromaDB persistence directory not found: {settings.chroma_persist_dir}")
        logger.error("Please ensure the vector store was created using 'scripts/ingest_vector_db.py'.")
        raise FileNotFoundError(f"ChromaDB directory not found: {settings.chroma_persist_dir}")

    try:
        logger.info(f"Connecting to vector store: {settings.chroma_persist_dir}")
        vectorstore = Chroma(
            persist_directory=str(settings.chroma_persist_dir),
            embedding_function=embeddings,
            collection_name=settings.chroma_collection_name
        )
        # k=5 means retrieve top 5 most relevant documents
        # score_threshold helps filter out irrelevant results
        retriever = vectorstore.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={'k': 5, 'score_threshold': 0.5}
        )
        logger.info("Vector store connected successfully.")
    except Exception as e:
        logger.error(f"Error connecting to Chroma DB: {e}")
        raise

    # --- Load Symptom Rules ---
    if not settings.symptom_rules_path.exists():
        logger.error(f"Symptom rules file not found: {settings.symptom_rules_path}")
        raise FileNotFoundError(f"Symptom rules file not found: {settings.symptom_rules_path}")
    try:
        logger.info(f"Loading symptom rules from: {settings.symptom_rules_path}")
        with open(settings.symptom_rules_path, 'r') as f:
            symptom_rules = json.load(f)
        logger.info("Symptom rules loaded successfully.")
    except Exception as e:
        logger.error(f"Error loading symptom rules: {e}")
        raise

    # --- Define Tools --- #
    tools = define_tools(retriever, symptom_rules) # Pass necessary components

    # --- Log Generated Tool Schemas for Debugging --- #
    try:
        tool_schemas = [format_tool_to_openai_tool(t) for t in tools]
        logger.info(f"Generated Tool Schemas: {json.dumps(tool_schemas, indent=2)}")
    except Exception as schema_ex:
        logger.warning(f"Could not generate or log tool schemas: {schema_ex}")

    # --- Define Agent Prompt --- #
    # Note: Gemini Tool Calling works best without explicit instructions to use tools in the prompt.
    # The model infers when to use them based on descriptions and function definitions.
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are MedAssist, a helpful and friendly AI medical assistant simulating a healthcare provider's assistant. "
         "Your goal is to provide informative answers to medical questions, help triage symptoms based on provided guidelines, and assist with scheduling or reminders. "
         "You are NOT a substitute for a real medical professional. Always state this clearly if providing medical information or advice. "
         "If a user describes potentially life-threatening symptoms (e.g., severe chest pain, difficulty breathing, uncontrolled bleeding, stroke symptoms), immediately advise them to call emergency services (like 911 in the US) or go to the nearest emergency room. Do not attempt to diagnose or treat emergencies. "
         "When answering questions using retrieved information, you MUST cite your sources clearly using the provided document metadata (e.g., [Source: MedlinePlus, Title: Diabetes]). "
         "Be concise, empathetic, and maintain a professional tone. Ask clarifying questions if the user's query is ambiguous. "
         "Do not provide information outside the scope of medicine, scheduling, or reminders."
         # "You have access to the following tools: {tool_names}" # Usually not needed for Gemini tool calling
         # "Think step-by-step about which tool to use, if any." # Internal thought process guidance
         ),
        # Restore history placeholder
        MessagesPlaceholder(variable_name="chat_history"),
        # Remove the extra placeholder
        # MessagesPlaceholder(variable_name="patient_id_context"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])

    # --- Create Agent --- #
    logger.info("Creating tool-calling agent...")
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True, # Keep verbose for basic flow logging
    )

    # Restore history wrapper
    agent_executor_with_history = RunnableWithMessageHistory(
        agent_executor,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
        # Ensure the db context is passed through the history wrapper if needed
        # This part might be tricky - let's assume tools get db independently for now
    )
    logger.info("Agent executor with history created.")

# --- Tool Definitions --- # #

# Simple RAG Tool using the retriever
@tool
def search_medical_knowledge(query: str) -> str:
    """Searches the medical knowledge base (MedlinePlus, openFDA) for information relevant to a medical query. Use this to answer general medical questions about conditions, drugs, symptoms, or treatments. Input is the user's medical question."""
    logger.info(f"Tool: search_medical_knowledge called with query: {query}")
    try:
        docs = retriever.invoke(query)
        # Format the results for the LLM, including metadata for citation
        context = "\n\n".join([
            f"Source: {doc.metadata.get('source', 'N/A')}, Title: {doc.metadata.get('title', 'N/A')}, URL: {doc.metadata.get('url', 'N/A')}\nContent: {doc.page_content[:1000]}..."
            for doc in docs
        ])
        if not context:
            return "No relevant information found in the knowledge base."
        logger.info(f"Retrieved {len(docs)} documents for RAG.")
        # Return the formatted context string - the LLM will synthesize the answer based on this + the prompt
        return context
    except Exception as e:
        logger.error(f"Error during vector store retrieval: {e}")
        return "Error searching knowledge base."

# Simple Symptom Triage Tool (Rule-based for now)
@tool
def triage_symptoms(symptoms_described: List[str], user_details: Optional[Dict[str, Any]] = None) -> str:
    """Analyzes a list of patient-described symptoms against predefined rules to suggest a triage level (ER, DoctorSoon, SelfCare). Returns a JSON string containing 'triage' and 'explanation'. Extracts symptoms like 'fever', 'rash', 'headache' from the conversation. Optionally uses `user_details` dictionary which might contain keys like 'age' (int) or 'temperature_c' (float) if provided."""
    logger.info(f"Tool: triage_symptoms called with symptoms: {symptoms_described}, details: {user_details}")
    if not symptom_rules:
        # Return error as JSON string
        return json.dumps({"triage": "Error", "explanation": "Symptom rules not loaded."})

    # Normalize symptoms (lowercase)
    symptoms_described = [s.lower() for s in symptoms_described]
    triage_result = {"triage": "SelfCare", "explanation": "Based on the information provided, self-care may be appropriate. Monitor your symptoms."} # Default

    # Basic Rule Matching Logic (enhance later)
    # 1. Check General Red Flags first
    for flag in symptom_rules.get('general_red_flags', []):
        if any(s in symptoms_described for s in flag.get('symptoms', [])):
            logger.info(f"Matched general red flag: {flag.get('explanation')}")
            return {"triage": flag.get('triage', 'ER'), "explanation": flag.get('explanation')} # Highest priority

    # 2. Check specific symptom rules
    matched_rules = []
    for symptom_key, rule_data in symptom_rules.get('symptoms', {}).items():
        if symptom_key.lower() in symptoms_described:
            # Check specific rules under this symptom
            for rule in rule_data.get('rules', []):
                conditions = rule.get('conditions', {})
                match = True
                # Basic condition matching - needs refinement!
                if "accompanied_by" in conditions:
                    if not all(s in symptoms_described for s in conditions["accompanied_by"]):
                        match = False
                # Add checks using the user_details dictionary
                if user_details:
                    # Check age if rule requires it and user provided it
                    if "min_age" in conditions:
                        user_age = user_details.get("age")
                        if not isinstance(user_age, int) or user_age < conditions["min_age"]:
                            match = False
                    # Check temperature if rule requires it and user provided it
                    if "temperature_c_above" in conditions:
                        user_temp = user_details.get("temperature_c")
                        if not isinstance(user_temp, (int, float)) or user_temp <= conditions["temperature_c_above"]:
                            match = False

                if match:
                    matched_rules.append({"triage": rule.get("triage"), "explanation": rule.get("explanation")})

    # Determine final triage (simple logic: take highest priority found)
    priority = {"ER": 3, "DoctorSoon": 2, "SelfCare": 1, None: 0}
    highest_priority_rule = {} # Default
    for rule in matched_rules:
        if priority.get(rule['triage'], 0) > priority.get(highest_priority_rule.get('triage'), 0):
            highest_priority_rule = rule

    if highest_priority_rule:
        triage_result = highest_priority_rule
        logger.info(f"Matched specific symptom rule: {triage_result}")
    else:
        logger.info("No specific rules matched, using default SelfCare.")
        # Consider LLM classification here if ambiguous and no rules matched

    # Return result as JSON string
    return json.dumps(triage_result)

# Placeholder DB tools (replace with calls to crud.py functions later)
@tool
def schedule_appointment(requested_time: str, patient_db_id: Optional[int], reason: Optional[str] = None) -> str:
    """Schedules an appointment for the patient. Use this tool ONLY if the user explicitly asks to book, schedule, or make an appointment. Requires the desired `requested_time` (like 'next Tuesday morning' or 'tomorrow at 3pm'). It also needs the internal `patient_db_id` for the user if they are known, otherwise this will be null for guest users. An optional `reason` for the visit can be included."""
    logger.info(f"Tool: schedule_appointment called for time: {requested_time} for patient_db_id: {patient_db_id}")

    # --- Handle Guest User --- #
    if patient_db_id is None:
        logger.warning("schedule_appointment tool called for guest user.")
        # Option 1: Disallow guest scheduling
        return "I cannot schedule appointments for guest users. Please register or log in first."
        # Option 2: Ask for more info (requires multi-turn tool interaction or different agent design)
        # return "To schedule an appointment as a guest, I need your name and phone number. Can you please provide them?"
    # ----------------------- #

    # Get a new DB session for this tool invocation
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        if not db:
            raise Exception("Failed to create database session.")

        # --- Validate Patient ID --- #
        # This block only runs if patient_db_id is not None
        logger.info(f"Using patient_db_id from context: {patient_db_id}")
        db_patient = crud.get_patient(db, patient_id=patient_db_id)
        if not db_patient:
            # This case should ideally be caught before invoking the tool
            logger.error(f"Patient with ID {patient_db_id} provided to tool not found.")
            return f"Error: Patient with internal ID {patient_db_id} not found."
        # ------------------------- #

        # --- Parse Time (using dateparser with relative base) --- #
        now = datetime.now()
        logger.info(f"Parsing time '{requested_time}' relative to {now}")
        appt_time = dateparser.parse(requested_time, settings={'RELATIVE_BASE': now})
        logger.info(f"Result of dateparser.parse for appt: {appt_time} (type: {type(appt_time)})") # Keep log
        if not appt_time:
            return f"Sorry, I couldn't understand the time '{requested_time}'. Please try specifying the date and time more clearly (e.g., 'next Tuesday at 3 PM', 'tomorrow morning')."
        # TODO: Add logic to find *next available* slot around appt_time, not just use the parsed time directly
        logger.info(f"Parsed requested_time '{requested_time}' to {appt_time}")
        # ---------------------------------------------------------- #

        appointment_data = schemas.AppointmentCreate(
            patient_id=patient_db_id,
            appointment_time=appt_time,
            reason=reason,
            provider_name="Dr. Placeholder" # Assign dynamically later
        )
        db_appointment = crud.create_appointment(db=db, appointment=appointment_data)
        logger.info(f"Successfully created appointment ID: {db_appointment.id} for patient {patient_db_id}")
        # Format time separately before the f-string
        formatted_time = appt_time.strftime("%A, %B %d at %I:%M %p")
        return f"OK. I have scheduled an appointment for patient ID {patient_db_id} on {formatted_time}. The reason is: {reason or 'not specified'}."

    except Exception as e:
        logger.error(f"Error in schedule_appointment tool: {e}", exc_info=True)
        return "Sorry, I encountered an error while trying to schedule the appointment."
    finally:
        if db: # Ensure session is closed
            db.close()

@tool
def set_reminder(reminder_details: str, reminder_time: str, patient_db_id: Optional[int]) -> str:
    """Sets a reminder. Use this tool ONLY if the user explicitly asks to set or create a reminder. Requires the `reminder_details` (e.g., 'Take antibiotic'), the `reminder_time` (e.g., 'every day at 8am' or 'in 3 hours'). The internal `patient_db_id` is needed if the user is known, otherwise it's null for guest users. Guest reminders are saved but cannot be delivered via email/SMS without registration."""
    logger.info(f"Tool: set_reminder called for patient_db_id {patient_db_id}, details: '{reminder_details}' at time: {reminder_time}")

    # Get a new DB session for this tool invocation
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        if not db:
            raise Exception("Failed to create database session.")

        # --- Validate Patient ID (Optional) --- #
        if patient_db_id is not None:
            logger.info(f"Using patient_db_id from context: {patient_db_id}")
            db_patient = crud.get_patient(db, patient_id=patient_db_id)
            if not db_patient:
                logger.error(f"Patient with ID {patient_db_id} provided to tool not found.")
                return f"Error: Patient with internal ID {patient_db_id} not found."
        else:
            logger.info("Setting reminder for a guest user (patient_db_id is None).")
        # ------------------------- #

        # --- Parse Time (using dateparser with relative base) --- #
        now = datetime.now()
        logger.info(f"Parsing reminder time '{reminder_time}' relative to {now}")
        due_at = dateparser.parse(reminder_time, settings={'RELATIVE_BASE': now})
        logger.info(f"Result of dateparser.parse for reminder: {due_at} (type: {type(due_at)})") # Keep log
        if not due_at:
            return f"Sorry, I couldn't understand the time '{reminder_time}' for the reminder."
        logger.info(f"Parsed reminder_time '{reminder_time}' to {due_at}")
        # ---------------------------------------------------------- #

        reminder_data = schemas.ReminderCreate(
            patient_id=patient_db_id, # Pass patient_db_id (which can be None)
            reminder_type="generic",
            message=reminder_details,
            due_at=due_at,
            method='system'
        )
        db_reminder = crud.create_reminder(db=db, reminder=reminder_data)
        logger.info(f"Successfully created reminder ID: {db_reminder.id} for patient ID: {patient_db_id or 'Guest'}")
        formatted_time = due_at.strftime("%A, %B %d at %I:%M %p")
        # Modify response based on whether it was a guest
        user_desc = f"patient ID {patient_db_id}" if patient_db_id else "guest user"
        confirmation_message = f"OK. I have set a reminder for {user_desc} for '{reminder_details}' on {formatted_time}."
        if patient_db_id is None:
            confirmation_message += " (Note: Guest reminders are logged but not delivered via email/SMS.)"
        return confirmation_message

    except Exception as e:
        logger.error(f"Error in set_reminder tool: {e}", exc_info=True)
        return "Sorry, I encountered an error while trying to set the reminder."
    finally:
        if db: # Ensure session is closed
            db.close()

def define_tools(retriever, symptom_rules_data):
    """Defines the list of tools available to the agent."""
    # Update tool functions if they need direct access to retriever or rules
    # (Alternatively, they can access the global vars if initialized)
    global symptom_rules # Ensure the tool uses the loaded rules
    symptom_rules = symptom_rules_data

    # Update RAG tool if it needs direct retriever access
    # (Current implementation uses global retriever)

    tools = [
        # Re-enable the RAG tool
        search_medical_knowledge,
        triage_symptoms,
        schedule_appointment,
        set_reminder
    ]
    return tools

# --- Main Agent Invocation Function --- #

async def get_agent_response(
    user_id: str,
    message: str,
    session_id: str,
    db: Optional[Session] = None
) -> schemas.ChatResponse:
    """
    Handles invoking the agent executor with memory and returning the response.
    Looks up internal patient ID based on the incoming user_id (synthea_id).
    Extracts sources from the final reply text using regex.
    (Note: Triage tag extraction from intermediate_steps is removed as steps are often empty)
    """
    logger.info(f"Agent received message: '{message}' for user: {user_id}, session: {session_id}")

    # --- Get Internal Patient ID --- #
    patient_db_id: Optional[int] = None
    if db:
        try:
            patient = crud.get_patient_by_synthea_id(db, synthea_id=user_id)
            if patient:
                patient_db_id = patient.id
                logger.info(f"Mapped user_id '{user_id}' to patient_db_id: {patient_db_id}")
            else:
                logger.warning(f"Could not find patient in DB for user_id (synthea_id): {user_id}")
        except Exception as e:
            logger.error(f"Database error looking up patient for user_id {user_id}: {e}")
    else:
        logger.warning("No DB session provided to get_agent_response, cannot look up patient ID.")
    # ----------------------------- #

    if not agent_executor_with_history:
        logger.error("Agent executor with history not initialized!")
        return schemas.ChatResponse(reply="Error: Agent not available.", session_id=session_id)

    extracted_sources: List[Dict[str, Any]] = []
    extracted_triage_tag: Optional[str] = None # Keep this, maybe set by other logic later?

    try:
        # Create instance of custom handler for this request
        triage_handler = TriageTagCaptureHandler(session_id=session_id)

        # Pass handlers via RunnableConfig
        config = RunnableConfig(
            configurable={"session_id": session_id},
            callbacks=[triage_handler]
        )

        # Prepare input, prepending patient context to the user message
        if patient_db_id is not None:
            context_prefix = f"(System Note: The user you are talking to corresponds to internal patient ID: {patient_db_id})\n\nUser Query: "
            final_input = context_prefix + message
            logger.info(f"Passing patient context prefixed to input: {context_prefix[:50]}...")
        else:
            context_prefix = "(System Note: User's patient ID is unknown.)\n\nUser Query: "
            final_input = context_prefix + message
            logger.warning("No patient_db_id found, passing unknown context prefix.")
        agent_input = {"input": final_input}

        # Invoke the agent with history and callbacks
        agent_response = await agent_executor_with_history.ainvoke(
            agent_input,
            config=config
        )

        # --- Process Agent Output --- #
        reply_text = agent_response.get('output', "Sorry, I encountered an issue processing that.")

        # --- Extract Sources from Reply Text using Regex --- #
        # Regex to find patterns like [Source: <Name>, Title: <Title>] or [Source: <Name>, URL: <URL>] etc.
        # This regex is basic and might need refinement based on observed output variations.
        source_pattern = r"\[Source: ([^,]+), (?:Title: ([^,\]]+)|URL: ([^,\]]+))(?:, (?:Title: ([^,\]]+)|URL: ([^,\]]+)))?\]"

        matches = re.finditer(source_pattern, reply_text)
        for match in matches:
            source, title1, url1, title2, url2 = match.groups()
            source_info = {"source": source.strip()}
            title = title1 or title2
            url = url1 or url2
            if title: source_info["title"] = title.strip()
            if url: source_info["url"] = url.strip()
            if source_info not in extracted_sources:
                extracted_sources.append(source_info)

        if extracted_sources:
            logger.info(f"Extracted sources via regex from reply: {extracted_sources}")
        # ------------------------------------------------- #

        # --- Get Triage Tag from Custom Callback Handler --- #
        extracted_triage_tag = triage_handler.get_captured_tag(session_id)
        if extracted_triage_tag:
             logger.info(f"Retrieved captured triage_tag '{extracted_triage_tag}' from handler for session {session_id}")
        else:
            logger.info(f"No triage tag was captured by the handler for session {session_id}")
        # -------------------------------------------------- #

        response = schemas.ChatResponse(
            reply=reply_text,
            session_id=session_id,
            sources=extracted_sources if extracted_sources else None,
            triage_tag=extracted_triage_tag # Assign the extracted tag
        )

    except Exception as e:
        logger.error(f"Error invoking agent for session {session_id}: {e}", exc_info=True)
        response = schemas.ChatResponse(
            reply="Sorry, I encountered an error. Please try again.",
            session_id=session_id,
            sources=None,
            triage_tag=None
        )

    logger.info(f"Agent generated response for user: {user_id}, session: {session_id}")
    return response

# --- Initialize components when module loads --- #
# Ensures that components are ready before the first request
# You might move this call to the FastAPI startup event later
initialize_agent_components() 