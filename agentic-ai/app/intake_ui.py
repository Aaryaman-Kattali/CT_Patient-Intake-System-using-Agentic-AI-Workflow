"""
Patient Intake Agent Chat Application
====================================

This Streamlit application provides a chat interface for interacting with the ADK Patient Intake Agent.
It uses Streamlit's built-in chat elements (st.chat_message and st.chat_input) for a proper chat experience.
It allows users to handle patient intake processes, create sessions, and interact with multiple subagents
(data collection agent and email agent) through a unified interface.

Requirements:
------------
- ADK API Server running on localhost:8000
- Patient Intake Agent (agent) registered and available in the ADK
- Streamlit and related packages installed

Usage:
------
1. Start the ADK API Server: `adk api_server`
2. Ensure the Patient Intake Agent is registered and working
3. Run this Streamlit app: `streamlit run app/intake_ui.py`
4. Click "Create Session" in the sidebar
5. Start the patient intake process

Architecture:
------------
- Session Management: Creates and manages ADK sessions for stateful conversations
- Message Handling: Sends user messages to the ADK API and processes responses
- Multi-Agent Support: Handles transfers between root agent and subagents
- Intake Process: Guides users through Family Inquiry or Provider Referral workflows

API Assumptions:
--------------
1. ADK API Server runs on localhost:8000
2. Patient Intake Agent is registered with app_name="agent"
3. The system uses subagents: data_collector_agent and email_agent
4. Responses follow the ADK event structure with model outputs and function calls/responses
5. Agent transfers are handled via transfer_to_agent function calls

"""
import streamlit as st
import requests
import json
import uuid
import time
from datetime import datetime

# Set page configuration with appropriate theme for medical application
st.set_page_config(
    page_title="Patient Intake System",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants for API configuration
API_BASE_URL = "http://localhost:8000"
APP_NAME = "agent"  # Your main agent app name

# Initialize session state variables for maintaining conversation state
if "user_id" not in st.session_state:
    st.session_state.user_id = f"patient-{uuid.uuid4()}"
    
if "session_id" not in st.session_state:
    st.session_state.session_id = None
    
if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_agent" not in st.session_state:
    st.session_state.current_agent = "root_patient_intake_agent"

if "intake_type" not in st.session_state:
    st.session_state.intake_type = None

if "patient_data" not in st.session_state:
    st.session_state.patient_data = {}

def create_session():
    """
    Create a new session with the patient intake agent.
    
    This function:
    1. Generates a unique session ID based on timestamp
    2. Sends a POST request to the ADK API to create a session
    3. Updates the session state variables if successful
    4. Resets conversation history and patient data
    
    Returns:
        bool: True if session was created successfully, False otherwise
    
    API Endpoint:
        POST /apps/{app_name}/users/{user_id}/sessions/{session_id}
    """
    try:
        # Generate unique session ID with timestamp
        session_id = f"intake-session-{int(time.time())}"
        
        # Make API request to create session
        response = requests.post(
            f"{API_BASE_URL}/apps/{APP_NAME}/users/{st.session_state.user_id}/sessions/{session_id}",
            headers={"Content-Type": "application/json"},
            data=json.dumps({}),
            timeout=10
        )
        
        if response.status_code == 200:
            # Update session state on successful creation
            st.session_state.session_id = session_id
            st.session_state.messages = []
            st.session_state.current_agent = "root_patient_intake_agent"
            st.session_state.intake_type = None
            st.session_state.patient_data = {}
            
            # Add welcome message to start the conversation
            welcome_msg = {
                "role": "assistant", 
                "content": "Welcome to the Patient Intake System! I'm here to help you with your inquiry. To get started, please let me know if this is a Family Inquiry or a Provider Referral.",
                "agent": "root_patient_intake_agent",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
            st.session_state.messages.append(welcome_msg)
            
            return True
        else:
            st.error(f"Failed to create session: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        st.error(f"Network error while creating session: {str(e)}")
        return False
    except Exception as e:
        st.error(f"Unexpected error while creating session: {str(e)}")
        return False

def send_message(message):
    """
    Send a message to the patient intake agent and process the response.
    
    This function:
    1. Adds the user message to the chat history
    2. Sends the message to the ADK API
    3. Processes the response to extract text and function call information
    4. Handles agent transfers and updates current agent state
    5. Updates the chat history with the assistant's response
    
    Args:
        message (str): The user's message to send to the agent
        
    Returns:
        bool: True if message was sent and processed successfully, False otherwise
    
    API Endpoint:
        POST /run
        
    Response Processing:
        - Parses the ADK event structure to extract text responses
        - Looks for transfer_to_agent function calls to track agent changes
        - Looks for collect_data and send_email function responses
        - Handles multi-message responses from agent conversations
    """
    if not st.session_state.session_id:
        st.error("No active session. Please create a session first.")
        return False
    
    try:
        # Add user message to chat history
        user_msg = {
            "role": "user", 
            "content": message,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        st.session_state.messages.append(user_msg)
        
        # Prepare request payload for ADK API
        request_payload = {
            "app_name": APP_NAME,
            "user_id": st.session_state.user_id,
            "session_id": st.session_state.session_id,
            "new_message": {
                "role": "user",
                "parts": [{"text": message}]
            }
        }
        
        # Send message to API with timeout
        response = requests.post(
            f"{API_BASE_URL}/run",
            headers={"Content-Type": "application/json"},
            data=json.dumps(request_payload),
            timeout=30
        )
        
        if response.status_code != 200:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return False
        
        # Process the response events from ADK
        events = response.json()
        
        # Process each event in the response
        for event in events:
            process_event(event)
        
        return True
        
    except requests.exceptions.Timeout:
        st.error("Request timed out. Please try again.")
        return False
    except requests.exceptions.RequestException as e:
        st.error(f"Network error: {str(e)}")
        return False
    except json.JSONDecodeError:
        st.error("Invalid response format from server.")
        return False
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return False

def process_event(event):
    """
    Process individual events from the ADK API response.
    
    This function handles different types of events:
    - Model text responses
    - Function calls (transfer_to_agent, collect_data, send_email)
    - Function responses
    - Agent state changes
    
    Args:
        event (dict): Individual event from the ADK response
    """
    try:
        content = event.get("content", {})
        parts = content.get("parts", [])
        author = event.get("author", "unknown")
        
        # Process each part of the event content
        for part in parts:
            # Handle text responses from agents
            if "text" in part and part["text"].strip():
                assistant_msg = {
                    "role": "assistant",
                    "content": part["text"],
                    "agent": author,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
                st.session_state.messages.append(assistant_msg)
                
                # Update current agent based on author
                if author != "unknown":
                    st.session_state.current_agent = author
            
            # Handle function calls (outgoing from agent)
            elif "functionCall" in part:
                function_call = part["functionCall"]
                function_name = function_call.get("name", "")
                function_args = function_call.get("args", {})
                
                # Handle agent transfer function calls
                if function_name == "transfer_to_agent":
                    target_agent = function_args.get("agent_name", "")
                    if target_agent:
                        transfer_msg = {
                            "role": "system",
                            "content": f"🔄 Transferring to {target_agent.replace('_', ' ').title()}...",
                            "agent": "system",
                            "timestamp": datetime.now().strftime("%H:%M:%S")
                        }
                        st.session_state.messages.append(transfer_msg)
                
                # Handle data collection function calls
                elif function_name == "collect_data":
                    data_msg = {
                        "role": "system",
                        "content": "📋 Collecting patient data...",
                        "agent": "system",
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    }
                    st.session_state.messages.append(data_msg)
                
                # Handle email function calls
                elif function_name == "send_email":
                    email_msg = {
                        "role": "system",
                        "content": "📧 Sending email...",
                        "agent": "system",
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    }
                    st.session_state.messages.append(email_msg)
            
            # Handle function responses (incoming to agent)
            elif "functionResponse" in part:
                function_response = part["functionResponse"]
                function_name = function_response.get("name", "")
                
                # Handle transfer confirmation
                if function_name == "transfer_to_agent":
                    # Check if there's a transferToAgent action in the event
                    actions = event.get("actions", {})
                    if "transferToAgent" in actions:
                        target_agent = actions["transferToAgent"]
                        st.session_state.current_agent = target_agent
        
        # Handle agent transfer actions at event level
        actions = event.get("actions", {})
        if "transferToAgent" in actions:
            target_agent = actions["transferToAgent"]
            st.session_state.current_agent = target_agent
            
    except Exception as e:
        # Log processing errors but don't break the conversation
        st.error(f"Error processing event: {str(e)}")

def get_agent_display_name(agent_name):
    """
    Convert agent internal names to user-friendly display names.
    
    Args:
        agent_name (str): Internal agent name
        
    Returns:
        str: User-friendly display name
    """
    agent_names = {
        "root_patient_intake_agent": "Intake Coordinator",
        "data_collector_agent": "Data Collection Specialist", 
        "email_agent": "Email Assistant",
        "system": "System",
        "unknown": "Assistant"
    }
    return agent_names.get(agent_name, agent_name.replace("_", " ").title())

def get_agent_avatar(agent_name):
    """
    Get avatar/emoji for different agents for better visual distinction.
    
    Args:
        agent_name (str): Internal agent name
        
    Returns:
        str: Emoji or character to use as avatar
    """
    agent_avatars = {
        "root_patient_intake_agent": "🏥",
        "data_collector_agent": "📋",
        "email_agent": "📧",
        "system": "⚙️",
        "unknown": "🤖"
    }
    return agent_avatars.get(agent_name, "🤖")

# Main UI Layout with styled header
st.markdown(
    """
    <div style="
        background: linear-gradient(90deg, #2E86AB 0%, #A23B72 100%);
        color: white;
        padding: 1rem 2rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    ">
        <h1 style="margin: 0; font-size: 2.5rem;">🏥 Patient Intake System</h1>
        <p style="margin: 0.5rem 0 0 0; font-style: italic; opacity: 0.9;">Streamlined patient intake process with intelligent agent assistance</p>
    </div>
    """,
    unsafe_allow_html=True
)

# Main UI Layout
#st.title("🏥 Patient Intake System")
#st.markdown("*Streamlined patient intake process with intelligent agent assistance*")

# Create sidebar for session management and system info
with st.sidebar:
    st.header("🏥 Patient Intake System")
    st.divider()    
    st.subheader("Session Management")
    
    # Display current session status
    if st.session_state.session_id:
        st.success("✅ Active Session")
        #st.caption(f"Session: {st.session_state.session_id}")
        #st.caption(f"User: {st.session_state.user_id}")
        
        # Show current agent
        current_agent_display = get_agent_display_name(st.session_state.current_agent)
        current_agent_avatar = get_agent_avatar(st.session_state.current_agent)
        st.info(f"{current_agent_avatar} Current Agent: {current_agent_display}")
        
        # New session button
        if st.button("🔄 New Session", help="Start a fresh intake session"):
            if create_session():
                st.rerun()
    else:
        st.warning("⚠️ No Active Session")
        if st.button("▶️ Start Session", help="Begin patient intake process"):
            if create_session():
                st.rerun()
    
    st.divider()
    
    # System status information
    st.subheader("System Status")
    
    # Check API server connectivity
    try:
        health_response = requests.get(f"{API_BASE_URL}/list-apps", timeout=5)
        if health_response.status_code == 200:
            st.success("🟢 API Server Online")
            apps = health_response.json()
            if APP_NAME in apps:
                st.success(f"✅ {APP_NAME} Available")
            else:
                st.warning(f"⚠️ {APP_NAME} Not Found")
        else:
            st.error("🔴 API Server Error")
    except:
        st.error("🔴 API Server Offline")
    
    st.divider()
    
    # Quick action buttons for common intake types
    # st.subheader("Quick Actions")
    # if st.session_state.session_id:
    #     if st.button("👨‍👩‍👧‍👦 Family Inquiry", help="Start family inquiry process"):
    #         if send_message("This is a Family Inquiry"):
    #             st.rerun()
            
    #     if st.button("🏥 Provider Referral", help="Start provider referral process"):
    #         if send_message("This is a Provider Referral"):
    #             st.rerun()
    # else:
    #     st.caption("Create a session to use quick actions")
        
    # Helpful tips
    with st.expander("💡 Usage Tips"):
        st.markdown("""
        **Getting Started:**
        - Specify if this is a "Family Inquiry" or "Provider Referral"
        - The system will guide you through the appropriate workflow
        
        **During Data Collection:**
        - Provide accurate patient information when requested
        - The data collector will ask for specific details step by step
        
        **Email Process:**
        - Confirmation emails will be sent automatically
        - You'll be notified when emails are sent successfully
        
        **Agent Transfers:**
        - The system automatically transfers you between specialists
        - Each agent has specific expertise (intake, data collection, email)
        """)

# Main chat interface
st.subheader("💬 Conversation")

# Display chat messages from history using Streamlit's native chat components
if st.session_state.messages:
    for message in st.session_state.messages:
        if message["role"] == "user":
            # Display user messages
            with st.chat_message("user"):
                st.markdown(message["content"])
                if message.get("timestamp"):
                    st.caption(f"⏰ {message['timestamp']}")
                    
        elif message["role"] == "system":
            # Display system messages with custom avatar
            with st.chat_message("assistant", avatar="⚙️"):
                st.markdown(f"*{message['content']}*")
                if message.get("timestamp"):
                    st.caption(f"⏰ {message['timestamp']}")
                    
        else:  # assistant messages
            # Get agent-specific avatar and display name
            agent_name = message.get("agent", "unknown")
            agent_avatar = get_agent_avatar(agent_name)
            agent_display = get_agent_display_name(agent_name)
            
            with st.chat_message("assistant", avatar=agent_avatar):
                # Show which agent is responding
                st.markdown(f"**{agent_display}:**")
                st.markdown(message["content"])
                if message.get("timestamp"):
                    st.caption(f"⏰ {message['timestamp']}")
else:
    # Show placeholder when no messages and no session
    if not st.session_state.session_id:
        st.info("👋 Welcome! Create a session to start the patient intake process.")
    else:
        # Show the welcome message area
        st.info("💬 Session created! Start chatting below.")

# Chat input - only show if session exists
if st.session_state.session_id:
    # Use Streamlit's native chat input
    if prompt := st.chat_input(
        "Type your message here...",
        key="chat_input"
    ):
        # Send the message and rerun to update the chat
        if send_message(prompt):
            st.rerun()
else:
    # Show disabled chat input with instructions
    st.chat_input(
        "Please create a session first to start chatting...",
        disabled=True,
        key="disabled_chat_input"
    )

# Footer with additional information
st.divider()
# st.markdown(
#     """
#     <div style="text-align: center; color: #666; font-size: 0.8em; padding: 20px;">
#         Patient Intake System | Powered by ADK Multi-Agent Architecture<br>
#         For technical support, ensure the ADK API Server is running on port 8000
#     </div>
#     """, 
#     unsafe_allow_html=True
# )
