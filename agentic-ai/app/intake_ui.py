"""
Patient Intake Agent Chat Application
====================================

This Streamlit application provides a chat interface for interacting with the ADK Patient Intake Agent.
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

def get_agent_color(agent_name):
    """
    Get color coding for different agents for better visual distinction.
    
    Args:
        agent_name (str): Internal agent name
        
    Returns:
        str: CSS color value
    """
    agent_colors = {
        "root_patient_intake_agent": "#2E86AB",  # Blue
        "data_collector_agent": "#A23B72",      # Purple
        "email_agent": "#F18F01",               # Orange
        "system": "#6C757D",                    # Gray
        "unknown": "#6C757D"                    # Gray
    }
    return agent_colors.get(agent_name, "#6C757D")

# Main UI Layout
st.title("🏥 Patient Intake System")
st.markdown("*Streamlined patient intake process with intelligent agent assistance*")

# Create two columns for better layout
col1, col2 = st.columns([3, 1])

with col2:
    # Sidebar for session management and system info
    st.subheader("Session Management")
    
    # Display current session status
    if st.session_state.session_id:
        st.success("✅ Active Session")
        st.caption(f"Session: {st.session_state.session_id}")
        st.caption(f"User: {st.session_state.user_id}")
        
        # Show current agent
        current_agent_display = get_agent_display_name(st.session_state.current_agent)
        st.info(f"🤖 Current Agent: {current_agent_display}")
        
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
    st.subheader("Quick Actions")
    if st.session_state.session_id:
        if st.button("👨‍👩‍👧‍👦 Family Inquiry", help="Start family inquiry process"):
            send_message("This is a Family Inquiry")
            st.rerun()
            
        if st.button("🏥 Provider Referral", help="Start provider referral process"):
            send_message("This is a Provider Referral")
            st.rerun()
    else:
        st.caption("Create a session to use quick actions")

with col1:
    # Main chat interface
    st.subheader("💬 Conversation")
    
    # Create a container for messages with custom styling
    message_container = st.container()
    
    with message_container:
        # Display conversation history
        if st.session_state.messages:
            for i, msg in enumerate(st.session_state.messages):
                # Determine message type and styling
                if msg["role"] == "user":
                    # User messages - right aligned with blue background
                    st.markdown(
                        f"""
                        <div style="text-align: right; margin: 10px 0;">
                            <div style="display: inline-block; background-color: #E3F2FD; 
                                    padding: 10px 15px; border-radius: 18px; max-width: 70%;
                                    border: 1px solid #BBDEFB;">
                                <strong style="color: #000000;">You:</strong> <span style="color: #000000;">{msg['content']}</span><br>
                                <small style="color: #666;">{msg.get('timestamp', '')}</small>
                            </div>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                
                elif msg["role"] == "system":
                    # System messages - centered with gray background
                    st.markdown(
                        f"""
                        <div style="text-align: center; margin: 15px 0;">
                            <div style="display: inline-block; background-color: #F5F5F5; 
                                      padding: 8px 12px; border-radius: 12px; 
                                      border: 1px solid #E0E0E0; font-style: italic;">
                                {msg['content']}
                                <br><small style="color: #666;">
                                {msg.get('timestamp', '')}</small>
                            </div>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                
                else:
                    # Assistant messages - left aligned with agent-specific colors
                    agent_name = msg.get("agent", "unknown")
                    agent_display = get_agent_display_name(agent_name)
                    agent_color = get_agent_color(agent_name)
                    
                    st.markdown(
                        f"""
                        <div style="text-align: left; margin: 10px 0;">
                            <div style="display: inline-block; background-color: white; 
                                    padding: 10px 15px; border-radius: 18px; max-width: 80%;
                                    border-left: 4px solid {agent_color}; 
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                <strong style="color: {agent_color};">{agent_display}:</strong><br>
                                <span style="color: #000000;">{msg['content']}</span><br>
                                <small style="color: #666;">{msg.get('timestamp', '')}</small>
                            </div>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
        else:
            # Show placeholder when no messages
            st.info("👋 Welcome! Create a session to start the patient intake process.")
    
    # Message input area
    st.divider()
    
    # Only show input if session exists
    if st.session_state.session_id:
        # Create input form
        with st.form(key="message_form", clear_on_submit=True):
            col_input, col_send = st.columns([4, 1])
            
            with col_input:
                user_input = st.text_area(
                    "Your message:",
                    placeholder="Type your message here... (e.g., 'This is a Family Inquiry' or ask questions about the intake process)",
                    height=80,
                    key="user_message_input"
                )
            
            with col_send:
                st.markdown("<br>", unsafe_allow_html=True)  # Add spacing
                send_button = st.form_submit_button("📤 Send", use_container_width=True)
            
            # Handle form submission
            if send_button and user_input.strip():
                if send_message(user_input.strip()):
                    st.rerun()
                    
        # Helpful tips
        with st.expander("💡 Tips for using the system"):
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
    else:
        st.info("👆 Please create a session first to start chatting with the intake system.")

# Footer with additional information
st.divider()
st.markdown(
    """
    <div style="text-align: center; color: #666; font-size: 0.8em;">
        Patient Intake System | Powered by ADK Multi-Agent Architecture<br>
        For technical support, ensure the ADK API Server is running on port 8000
    </div>
    """, 
    unsafe_allow_html=True
)