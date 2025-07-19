# """
# Direct ADK Session Management - No Custom Wrapper
# =================================================

# This uses ADK's InMemorySessionService directly without custom wrappers.
# Simpler, more direct approach following ADK patterns exactly.
# """

# import json
# import uuid
# import time
# from datetime import datetime, timezone
# from typing import Dict, Any, Optional, List, Union
# from dataclasses import dataclass, asdict

# # Import ADK components
# from google.adk.sessions import InMemorySessionService, Session
# from google.adk.events import Event, EventActions
# from google.adk.agents import LlmAgent
# from google.adk.agents.callback_context import CallbackContext
# from google.adk.runners import Runner
# from google.genai.types import Content, Part

# # Initialize ADK session service directly
# session_service = InMemorySessionService()
# app_name = "multi_agent_intake_system"

# # =============================================================================
# # DIRECT ADK SESSION FUNCTIONS
# # =============================================================================

# async def create_or_get_session(user_id: str, session_id: Optional[str] = None) -> Session:
#     """Create new session or retrieve existing one using direct ADK."""
#     try:
#         if session_id:
#             # Try to get existing session
#             try:
#                 existing_session = await session_service.get_session(
#                     app_name=app_name,
#                     user_id=user_id,
#                     session_id=session_id
#                 )
#                 print(f"📋 Retrieved existing session: {session_id}")
#                 return existing_session
#             except Exception as e:
#                 print(f"⚠️ Could not retrieve session {session_id}: {e}")
        
#         # Create new session with initial state
#         initial_state = {
#             # CRITICAL: Add user_id to state for ADK context injection
#             "user_id": user_id,  # ADD THIS LINE
            
#             # Session-specific state
#             "intake_stage": "initial",
#             "current_agent": None,
#             "agents_history": [],
#             "client_data": {},
#             "data_collected": False,
#             "email_sent": False,
#             "created_at": datetime.now(timezone.utc).isoformat(),
            
#             # User-specific state (user: prefix)
#             "user:session_count": 1,
#             "user:last_interaction": datetime.now(timezone.utc).isoformat(),
#             "user:user_id": user_id,  # ADD THIS LINE TOO
            
#             # App-specific state (app: prefix) 
#             "app:workflow_version": "1.0",
#             "app:system_status": "active"
#         }
        
#         session = await session_service.create_session(
#             app_name=app_name,
#             user_id=user_id,
#             session_id=session_id,
#             state=initial_state
#         )
        
#         print(f"✅ Created new ADK session: {session.id}")
#         return session
        
#     except Exception as e:
#         print(f"❌ Session creation/retrieval failed: {e}")
#         raise

# async def update_session_state(session: Session, state_changes: Dict[str, Any], 
#                              author: str = "system", description: str = "State update") -> Session:
#     """Update session state using direct ADK EventActions.state_delta."""
#     try:
#         # Create EventActions with state_delta
#         actions_with_update = EventActions(state_delta=state_changes)
        
#         # Create event with proper structure
#         update_event = Event(
#             invocation_id=f"state_update_{int(time.time())}",
#             author=author,
#             actions=actions_with_update,
#             timestamp=time.time(),
#             content=Content(parts=[Part(text=description)])
#         )
        
#         # Append event to session (this updates the state)
#         await session_service.append_event(session, update_event)
        
#         # Get updated session
#         updated_session = await session_service.get_session(
#             app_name=app_name,
#             user_id=session.user_id,
#             session_id=session.id
#         )
        
#         print(f"📝 Updated session state: {list(state_changes.keys())}")
#         return updated_session
        
#     except Exception as e:
#         print(f"❌ State update failed: {e}")
#         raise

# async def handoff_to_agent(session: Session, agent_name: str, 
#                          handoff_data: Optional[Dict] = None) -> Session:
#     """Hand off session to another agent using direct ADK."""
#     try:
#         current_state = session.state
#         previous_agent = current_state.get("current_agent")
        
#         # Prepare state changes
#         state_changes = {
#             "current_agent": agent_name,
#             "updated_at": datetime.now(timezone.utc).isoformat(),
#             # Add to agents history (append to existing list)
#             "agents_history": current_state.get("agents_history", []) + [{
#                 "agent": agent_name,
#                 "timestamp": datetime.now(timezone.utc).isoformat(),
#                 "previous_agent": previous_agent,
#                 "handoff_data": handoff_data or {}
#             }]
#         }
        
#         # Update session using direct ADK
#         updated_session = await update_session_state(
#             session, 
#             state_changes, 
#             author="system",
#             description=f"Agent handoff from {previous_agent} to {agent_name}"
#         )
        
#         print(f"🔄 Session {session.id} handed off from {previous_agent} to {agent_name}")
#         return updated_session
        
#     except Exception as e:
#         print(f"❌ Agent handoff failed: {e}")
#         raise

# # =============================================================================
# # AGENT HELPER FUNCTIONS
# # =============================================================================

# async def get_session_for_agent(agent_name: str, user_id: str, session_id: Optional[str] = None) -> Dict:
#     """Get or create session for an agent using direct ADK."""
#     try:
#         # Get or create session
#         session = await create_or_get_session(user_id, session_id)
        
#         # Hand off to requesting agent
#         updated_session = await handoff_to_agent(session, agent_name)
        
#         return {
#             "status": "success",
#             "session": updated_session,
#             "session_id": updated_session.id,
#             "agent_name": agent_name,
#             "client_data": updated_session.state.get("client_data", {}),
#             "workflow_state": {
#                 "intake_stage": updated_session.state.get("intake_stage"),
#                 "data_collected": updated_session.state.get("data_collected", False),
#                 "email_sent": updated_session.state.get("email_sent", False)
#             }
#         }
        
#     except Exception as e:
#         print(f"❌ Session error for agent '{agent_name}': {e}")
#         return {
#             "status": "error",
#             "message": f"Session management failed: {str(e)}"
#         }

# async def get_session_with_user_id(app_name: str, user_id: str, session_id: str) -> Session:
#     """Get session and ensure user_id is in state for ADK context."""
#     try:
#         # FIXED: Use session_service.get_session instead of recursive call
#         session = await session_service.get_session(
#             app_name=app_name,
#             user_id=user_id,
#             session_id=session_id
#         )
        
#         # Ensure user_id is in session state
#         session = await ensure_user_id_in_session(session, user_id)
        
#         return session
        
#     except Exception as e:
#         print(f"❌ Error getting session with user_id: {e}")
#         raise

# async def update_client_data_in_session(session_id: str, user_id: str, client_data: Dict) -> bool:
#     """Update client data using direct ADK state management."""
#     try:
#         # Get current session with proper error handling
#         session = await get_session_with_user_id(app_name, user_id, session_id)
        
#         # Merge with existing client_data
#         current_client_data = session.state.get("client_data", {})
#         current_client_data.update(client_data)
        
#         # Update using direct ADK
#         state_changes = {
#             "client_data": current_client_data,
#             "updated_at": datetime.now(timezone.utc).isoformat()
#         }
        
#         await update_session_state(
#             session, 
#             state_changes,
#             author="data_collector_agent",
#             description="Updated client data"
#         )
        
#         print(f"✅ Updated client data in session {session_id}")
#         return True
        
#     except Exception as e:
#         print(f"❌ Error updating client data: {e}")
#         return False

# async def mark_stage_complete(session_id: str, user_id: str, stage: str, 
#                             completion_data: Optional[Dict] = None) -> bool:
#     """Mark a workflow stage as complete using direct ADK."""
#     try:
#         # Get current session
#         session = await get_session_with_user_id(app_name, user_id, session_id)
        
#         # Prepare state changes based on stage
#         state_changes = {
#             "intake_stage": stage,
#             "updated_at": datetime.now(timezone.utc).isoformat()
#         }
        
#         if stage == "data_collection_complete":
#             state_changes["data_collected"] = True
#         elif stage == "email_sent":
#             state_changes["email_sent"] = True
#         elif stage == "workflow_complete":
#             state_changes["data_collected"] = True
#             state_changes["email_sent"] = True
#             state_changes["status"] = "completed"
        
#         # Add completion data if provided
#         if completion_data:
#             state_changes.update(completion_data)
        
#         # Update session
#         await update_session_state(
#             session,
#             state_changes,
#             author="system",
#             description=f"Stage '{stage}' marked complete"
#         )
        
#         return True
        
#     except Exception as e:
#         print(f"❌ Error marking stage complete: {e}")
#         return False

# # =============================================================================
# # AGENT CALLBACK FUNCTIONS
# # =============================================================================

# def data_collection_callback(context: CallbackContext, collected_data: Dict):
#     """Callback function for data collection agent using CallbackContext.state."""
#     # Update client data using context.state (proper ADK way)
#     current_client_data = context.state.get("client_data", {})
#     current_client_data.update(collected_data)
#     context.state["client_data"] = current_client_data
    
#     # Update workflow state
#     context.state["data_collected"] = True
#     context.state["intake_stage"] = "data_collection_complete"
#     context.state["updated_at"] = datetime.now(timezone.utc).isoformat()
    
#     print(f"📝 Data collection callback updated state with: {list(collected_data.keys())}")

# def email_completion_callback(context: CallbackContext, email_details: Dict):
#     """Callback function for email agent completion using CallbackContext.state."""
#     # Update email status using context.state
#     context.state["email_sent"] = True
#     context.state["email_details"] = email_details
#     context.state["intake_stage"] = "workflow_complete"
#     context.state["status"] = "completed"
#     context.state["updated_at"] = datetime.now(timezone.utc).isoformat()
    
#     print(f"📧 Email completion callback updated state")

# # =============================================================================
# # AGENT DEFINITIONS
# # =============================================================================

# def create_data_collector_agent():
#     """Create data collector agent with proper ADK configuration."""
#     return LlmAgent(
#         name="DataCollectorAgent",
#         model="gemini-2.0-flash",
#         instruction="""
#         You are a data collection agent for client intake.
#         Collect the following information:
#         - Client name
#         - Client email
#         - Client phone number
        
#         Ask for each piece of information clearly and store it when provided.
#         Once all data is collected, confirm with the client and mark collection complete.
#         """,
#         output_key="last_collection_response"  # Saves agent response to state
#     )

# def create_email_agent():
#     """Create email agent with proper ADK configuration."""
#     return LlmAgent(
#         name="EmailAgent", 
#         model="gemini-2.0-flash",
#         instruction="""
#         You are an email agent that sends welcome emails to new clients.
#         Use the client data from the session to personalize the email.
        
#         Format: 
#         - Greeting with client name
#         - Welcome message
#         - Next steps information
        
#         After composing, mark the email as sent.
#         """,
#         output_key="last_email_response"  # Saves agent response to state
#     )

# # =============================================================================
# # SESSION CONTEXT TOOL
# # =============================================================================

# async def get_session_context_for_tools(session_id: str, user_id: str) -> Dict:
#     """Get current session context for tools using direct ADK."""
#     try:
#         session = await get_session_with_user_id(app_name, user_id, session_id)
        
#         client_data = session.state.get("client_data", {})
        
#         return {
#             "status": "success",
#             "context": {
#                 "session_id": session.id,
#                 "user_id": session.state.get("user_id", user_id),  # ADDED
#                 "current_agent": session.state.get("current_agent"),
#                 "client_name": client_data.get("client_name"),
#                 "client_email": client_data.get("client_email"), 
#                 "client_phone": client_data.get("client_phone"),
#                 "data_collected": session.state.get("data_collected", False),
#                 "email_sent": session.state.get("email_sent", False),
#                 "intake_stage": session.state.get("intake_stage", "initial"),
#                 "created_at": session.state.get("created_at"),
#                 "updated_at": session.state.get("updated_at")
#             }
#         }
#     except Exception as e:
#         return {"status": "error", "message": str(e)}

# async def validate_session_exists(session_id: str, user_id: str) -> bool:
#     """Validate that a session exists and is accessible."""
#     try:
#         await session_service.get_session(
#             app_name=app_name,
#             user_id=user_id,
#             session_id=session_id
#         )
#         return True
#     except Exception:
#         return False

# # =============================================================================
# # RUNNER-BASED AGENT EXECUTION
# # =============================================================================

# async def run_data_collector_agent(user_id: str, user_message: str, session_id: Optional[str] = None) -> Dict:
#     """Run data collector agent using ADK Runner with direct session management."""
#     try:
#         # Create agent
#         agent = create_data_collector_agent()
        
#         # Create runner
#         runner = Runner(
#             agent=agent,
#             app_name=app_name,
#             session_service=session_service  # Direct ADK session service
#         )
        
#         # Get or create session
#         session = await create_or_get_session(user_id, session_id)
        
#         # Hand off to data collector
#         session = await handoff_to_agent(session, "data_collector_agent")
        
#         # Run agent with user message
#         user_content = Content(parts=[Part(text=user_message)])
        
#         final_response = None
#         async for event in runner.run(
#             user_id=user_id,
#             session_id=session.id,
#             new_message=user_content
#         ):
#             if event.is_final_response():
#                 final_response = event.content
        
#         return {
#             "status": "success",
#             "session_id": session.id,
#             "response": final_response,
#             "agent": "data_collector_agent"
#         }
        
#     except Exception as e:
#         print(f"❌ Data collector agent failed: {e}")
#         return {"status": "error", "message": str(e)}

# async def run_email_agent(user_id: str, session_id: str) -> Dict:
#     """Run email agent using existing session with direct ADK."""
#     try:
#         # Create agent
#         agent = create_email_agent()
        
#         # Create runner
#         runner = Runner(
#             agent=agent,
#             app_name=app_name,
#             session_service=session_service  # Direct ADK session service
#         )
        
#         # Get existing session
#         session = await get_session_with_user_id(app_name, user_id, session_id)
        
#         # Hand off to email agent
#         session = await handoff_to_agent(session, "email_agent")
        
#         # Create message for email agent (using client data from session)
#         client_data = session.state.get("client_data", {})
#         email_instruction = f"Send welcome email to {client_data.get('client_name', 'client')} at {client_data.get('client_email', 'email')}"
        
#         user_content = Content(parts=[Part(text=email_instruction)])
        
#         final_response = None
#         async for event in runner.run(
#             user_id=user_id,
#             session_id=session.id,
#             new_message=user_content
#         ):
#             if event.is_final_response():
#                 final_response = event.content
        
#         # Mark email as sent
#         await mark_stage_complete(session.id, user_id, "workflow_complete", {
#             "email_sent": True,
#             "email_details": {"sent_at": datetime.now(timezone.utc).isoformat()}
#         })
        
#         return {
#             "status": "success",
#             "session_id": session.id,
#             "response": final_response,
#             "agent": "email_agent",
#             "workflow_complete": True
#         }
        
#     except Exception as e:
#         print(f"❌ Email agent failed: {e}")
#         return {"status": "error", "message": str(e)}
    
# async def ensure_user_id_in_session(session: Session, user_id: str) -> Session:
#     """Ensure user_id is available in session state for ADK context injection."""
#     try:
#         current_state = session.state
        
#         # Check if user_id is missing from state
#         if "user_id" not in current_state:
#             state_changes = {
#                 "user_id": user_id,
#                 "user:user_id": user_id,  # Also add with user: prefix
#                 "updated_at": datetime.now(timezone.utc).isoformat()
#             }
            
#             # Update session state
#             updated_session = await update_session_state(
#                 session, 
#                 state_changes, 
#                 author="system",
#                 description=f"Added user_id context for ADK injection"
#             )
            
#             print(f"✅ Added user_id '{user_id}' to session state for ADK context")
#             return updated_session
        
#         return session
        
#     except Exception as e:
#         print(f"❌ Error ensuring user_id in session: {e}")
#         return session
    


# # Export the main functions
# __all__ = [
#     'session_service',  # Export the ADK session service directly
#     'get_session_for_agent',
#     'update_client_data_in_session',
#     'mark_stage_complete',
#     'get_session_context_for_tools',
#     'run_data_collector_agent',
#     'run_email_agent',
#     'data_collection_callback',
#     'email_completion_callback'
# ]


#session_service.py
from google.adk.sessions import InMemorySessionService, Session
from google.adk.runners import Runner
from google.adk.agents import LlmAgent
from google.genai.types import Content, Part
from datetime import date, datetime, timezone
import uuid
import asyncio

session_service = InMemorySessionService()
print("✅ New InMemorySessionService created for state demonstration.")

SESSION_ID = str(uuid.uuid4())
USER_ID = datetime.now().strftime('%d%m%Y%H%M')  # Fixed: remove {} for string
APP_NAME = "Patient Intake Coordinator"

print(f"📋 Generated Session ID: {SESSION_ID}")
print(f"👤 Generated User ID: {USER_ID}")

#session = None
session = session_service.create_session(
    session_id=SESSION_ID,
    user_id=USER_ID,
    app_name=APP_NAME,
)

print(f"✅ Session created successfully")
print(f"📋 Session ID: {SESSION_ID}")
print(f"👤 User ID: {USER_ID}")
print(f"📱 App Name: {APP_NAME}")

# Create your agent
# intake_agent = LlmAgent(
#     name="PatientIntakeAgent",
#     model="gemini-2.0-flash", 
#     instruction="You are a patient intake coordinator. Collect patient name, email, and phone number."
# )

# Create runner
# runner = Runner(
#     agent=intake_agent,
#     app_name=APP_NAME,
#     session_service=session_service
# )

# # Run it
# for event in runner.run(
#     user_id=USER_ID,
#     session_id=SESSION_ID,
#     new_message= Content(parts=[Part(text="Hello, I need to schedule an appointment")])
# ):
#     if event.is_final_response():
#         print(event.content)

# Export the session instance so other agents can use it directly
__all__ = ['session_service', 'session', 'SESSION_ID', 'USER_ID', 'APP_NAME']