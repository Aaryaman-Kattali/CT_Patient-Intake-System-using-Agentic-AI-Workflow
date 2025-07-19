#data collector agent
from typing import Literal, Optional, Dict
from datetime import date, datetime, timezone
from pydantic import BaseModel
from google.adk.agents import LlmAgent
from pathlib import Path

from model.session_service import session_service, session, SESSION_ID, USER_ID, APP_NAME
from dotenv import load_dotenv
import json
import os
import re

# Load .env from root_agent
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)

# ----------------------
# Type Definition
# ----------------------

ReferralType: Literal["Self-Referral", "Physician Referral", "Specialist Referral", "Emergency Referral"]
ReferralMode: Literal["Fax", "Phone", "Webforms"]

# ---------------------------------
# Schema Functions
# ---------------------------------

def get_provider_schema() -> dict:
    """
    Returns the schema definition for collecting provider referral information.


    This is used by the agent to dynamically generate questions to ask the user.


    Returns:
        dict: Schema with field names, types, and allowed values (for dropdowns).
    """
    return {
        "status": "success",
        "schema": {
            "client_name": {
                "type": "string",
                "description": "Name of the patient/client"
            },
            "client_dob": {
                "type": "string",
                "description": "Date of birth of the patient/client in YYYY-MM-DD format"
            },
            "client_gender": {
                "type": "string",
                "description": "Gender of the patient/client, either Male or Female"
            },
            "client_email": {
                "type": "string",
                "description": "Email address of the patient/client"
            },
            "client_phone": {
                "type": "string",
                "description": "Phone number of the patient/client in XXX-XXX-XXXX format"
            },
            "client_address": {
                "type": "string",
                "description": "Address of the patient/client"
            },
            "referral_type": {
                "type": "dropdown",
                "options": ["Self-Referral", "Physician Referral", "Specialist Referral", "Emergency Referral"],
                "description": "Type of referral"
            },
            "referral_date": {
                "type": "date",
                "description": "Date of referral in YYYY-MM-DD format"
            },
            "referral_mode": {
                "type": "dropdown",
                "options": ["Fax", "Phone", "Webforms"],
                "description": "Mode used to send the referral"
            },
            "referral_provider_name": {
                "type": "string",
                "description": "Name of the referring provider"
            }
        }
    }

def get_inquiry_schema() -> dict:
    """
    Returns the schema definition for collecting family inquiry information.


    This is used by the agent to dynamically generate questions to ask the user.


    Returns:
        dict: Schema with field names, types, and allowed values (for dropdowns).
    """
    return {
        "status": "success",
        "schema": {
            "client_name": {
                "type": "string",
                "description": "Name of the patient/client"
            },
            "client_dob": {
                "type": "string",
                "description": "Date of birth of the patient/client in YYYY-MM-DD format"
            },
            "client_gender": {
                "type": "string",
                "description": "Gender of the patient/client, either Male or Female"
            },
            "client_email": {
                "type": "string",
                "description": "Email address of the patient/client"
            },
            "client_phone": {
                "type": "string",
                "description": "Phone number of the patient/client in XXX-XXX-XXXX format"
            },
            "client_address": {
                "type": "string",
                "description": "Address of the patient/client"
            },
            "relationship": {
                "type": "dropdown",
                "options": ["Self", "Parent", "Guardian", "Spouse", "Sibling", "Other Family Member"],
                "description": "Relationship to the client"
            },
            "inquiry_reason": {
                "type": "string",
                "description": "Reason for the inquiry"
            },
            "preferred_contact_method": {
                "type": "dropdown",
                "options": ["Phone", "Email", "Mail", "Text"],
                "description": "Preferred method of contact"
            },
            "contact_details": {
                "type": "string",
                "description": "Contact information (phone/email/address)"
            }
        }
    }


# ---------------------------
# Utility Functions (same as your original)
# ---------------------------

# def generate_next_user_id(directory: str = "collected_chatbot_data") -> str:
#     """Generate the next sequential user ID based on existing records."""
#     current_date = datetime.now().strftime("%d%m%Y")
    
#     if not os.path.exists(directory):
#         return f"01{current_date}"
    
#     existing_user_ids = []
    
#     for filename in os.listdir(directory):
#         if filename.endswith(".json"):
#             filepath = os.path.join(directory, filename)
#             try:
#                 with open(filepath, "r") as f:
#                     data = json.load(f)
#                     user_id = data.get("user_id")
#                     if user_id:
#                         existing_user_ids.append(user_id)
#             except Exception:
#                 continue
    
#     if not existing_user_ids:
#         return f"01{current_date}"
    
#     sequential_numbers = []
#     for user_id in existing_user_ids:
#         try:
#             seq_num = int(user_id[:2])
#             sequential_numbers.append(seq_num)
#         except (ValueError, IndexError):
#             continue
    
#     if sequential_numbers:
#         next_number = max(sequential_numbers) + 1
#     else:
#         next_number = 1
    
#     return f"{next_number:02d}{current_date}"

# ---------------------------------
# Exporting data in json
# ---------------------------------


def export_json_to_local(json_data: dict, filename: str, directory: str = "collected_chatbot_data") -> str:
    """Saves a dictionary as a JSON file in the specified local directory."""
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
            print(f"Created directory: {os.path.abspath(directory)}")
        except OSError as e:
            return f"Error creating directory {directory}: {e}"

    filepath = os.path.join(directory, f"{filename}.json")
   
    try:
        with open(filepath, "w") as f:
            json.dump(json_data, f, indent=4)
        return f"Successfully exported JSON data to {os.path.abspath(filepath)}"
    except TypeError as e:
        return f"Error: Provided data is not valid JSON or not a dictionary. {e}"
    except Exception as e:
        return f"Error exporting JSON data to {filepath}: {e}"

# def check_existing_client(client_name: str, client_phone: str, directory: str = "collected_chatbot_data") -> bool:
#     """Check for duplicate client entries."""
#     if not os.path.exists(directory):
#         return False

#     for filename in os.listdir(directory):
#         if filename.endswith(".json"):
#             filepath = os.path.join(directory, filename)
#             try:
#                 with open(filepath, "r") as f:
#                     data = json.load(f)
#                 if data.get("client_name", "").lower() == client_name.lower() and data.get("client_phone", "") == client_phone:
#                     return True
#             except Exception:
#                 continue
#     return False

# ---------------------------
# FIXED: Session Management
# ---------------------------

# async def get_or_create_session(user_id: Optional[str] = None) -> dict:
#     """Get or create a session for the data collector agent using direct ADK."""
#     try:
#         if not user_id:
#             user_id = generate_next_user_id()
#             print(f"🆔 Generated new user ID: {user_id}")
        
#         session = await create_or_get_session(user_id)
        
#         if "user_id" not in session.state:
#             await update_session_state(session, {"user_id": user_id}, "system", "Added user_id to session state")
        
#         return {
#             "status": "success",
#             "session_id": session.id,
#             "user_id": user_id,
#             "app_name": 'multi_agent_intake_system'
#         }
#     except Exception as e:
#         return {"status": "error", "message": f"Session management error: {e}"}

# ---------------------------
# Schema data storage
# ---------------------------

async def store_provider_data(
    client_name: str, client_dob: str, client_gender: str, client_email: str,
    client_phone: str, client_address: str, referral_type: str, referral_date: str,
    referral_mode: str, referral_provider_name: str
) -> dict:
    """Store provider referral data and update session."""
    
    # Validate inputs
    try:
        datetime.strptime(client_dob, '%Y-%m-%d')
        datetime.strptime(referral_date, '%Y-%m-%d')
        assert re.match(r'^\d{3}-\d{3}-\d{4}$', client_phone.strip())
    except (ValueError, AssertionError):
        return {"status": "error", "message": "Invalid date or phone format"}
    
    # Create data structure
    data = {
        "user_id": USER_ID,
        "client_name": client_name,
        "client_dob": client_dob,
        "client_gender": client_gender,
        "client_email": client_email,
        "client_phone": client_phone,
        "client_address": client_address,
        "referral_type": referral_type,
        "referral_date": referral_date,
        "referral_mode": referral_mode,
        "referral_provider_name": referral_provider_name,
        "record_type": "provider_referral",
        "created_at": datetime.now().isoformat()
    }
    
    # Save to file
    filename = f"referral_{USER_ID}_{client_name.replace(' ', '_').lower()}"
    save_result = export_json_to_local(data, filename)
    
    # CRITICAL: Update session state for email agent
    try:
        session.state["client_data"] = data
        session.state["data_collection_complete"] = True
        session.state["service_type"] = "provider_referral"
        session.state["client_name"] = client_name
        session.state["client_email"] = client_email
        session.state["ready_for_email"] = True
        
        print(f"✅ Provider data stored in session for {client_name}")
        return {
            "status": "success",
            "message": f"Provider referral data collected successfully. {save_result}",
            "ready_for_transfer": True
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Session update failed: {e}"}


async def store_inquiry_data(
    client_name: str, client_dob: str, client_gender: str, client_email: str,
    client_phone: str, client_address: str, relationship: str, inquiry_reason: str,
    preferred_contact_method: str, contact_details: str
) -> dict:
    """Store family inquiry data and update session."""
    
    # Validate inputs
    try:
        datetime.strptime(client_dob, '%Y-%m-%d')
        assert re.match(r'^\d{3}-\d{3}-\d{4}$', client_phone.strip())
    except (ValueError, AssertionError):
        return {"status": "error", "message": "Invalid date or phone format"}
    
    # Create data structure
    data = {
        "user_id": USER_ID,
        "client_name": client_name,
        "client_dob": client_dob,
        "client_gender": client_gender,
        "client_email": client_email,
        "client_phone": client_phone,
        "client_address": client_address,
        "relationship": relationship,
        "inquiry_reason": inquiry_reason,
        "preferred_contact_method": preferred_contact_method,
        "contact_details": contact_details,
        "record_type": "family_inquiry",
        "created_at": datetime.now().isoformat()
    }
    
    # Save to file
    filename = f"inquiry_{USER_ID}_{client_name.replace(' ', '_').lower()}"
    save_result = export_json_to_local(data, filename)
    
    # CRITICAL: Update session state for email agent
    try:
        session.state["client_data"] = data
        session.state["data_collection_complete"] = True
        session.state["service_type"] = "family_inquiry"
        session.state["client_name"] = client_name
        session.state["client_email"] = client_email
        session.state["ready_for_email"] = True
        
        print(f"✅ Inquiry data stored in session for {client_name}")
        return {
            "status": "success",
            "message": f"Family inquiry data collected successfully. {save_result}",
            "ready_for_transfer": True
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Session update failed: {e}"}
    
# ---------------------------------
# Check session state
# ---------------------------------

def check_session_state() -> dict:
    """Debug function to check current session state."""
    try:
        state_info = {
            "session_id": SESSION_ID,
            "user_id": USER_ID,
            "state_keys": list(session.state.keys()),
            "has_client_data": "client_data" in session.state,
            "data_collection_complete": session.state.get("data_collection_complete", False),
            "ready_for_email": session.state.get("ready_for_email", False)
        }
        
        if "client_data" in session.state:
            client_data = session.state["client_data"]
            state_info["client_name"] = client_data.get("client_name", "N/A")
            state_info["client_email"] = client_data.get("client_email", "N/A")
            state_info["service_type"] = session.state.get("service_type", "N/A")
        
        return {"status": "success", "session_info": state_info}
        
    except Exception as e:
        return {"status": "error", "message": f"Session check failed: {e}"}

# def debug_session_state_before_and_after() -> dict:
#     """Debug function to show session state before and after operations"""
#     try:
#         from model.session_service import session
        
#         # Use global session directly
#         current_state = dict(session.state)  # Make a copy
        
#         print(f"🔍 DEBUG SESSION STATE:")
#         print(f"Session ID: {SESSION_ID}")
#         print(f"Current state keys: {list(current_state.keys())}")
#         print(f"Has client_data: {'client_data' in current_state}")
        
#         if 'client_data' in current_state:
#             client_data = current_state['client_data']
#             print(f"Client name in session: {client_data.get('client_name', 'NO NAME')}")
#             print(f"Client email in session: {client_data.get('client_email', 'NO EMAIL')}")
        
#         return {
#             "status": "success",
#             "session_id": SESSION_ID,
#             "state_keys": list(current_state.keys()),
#             "has_client_data": 'client_data' in current_state,
#             "full_state": current_state
#         }
        
#     except Exception as e:
#         print(f"Error in debug function: {e}")
#         return {"status": "error", "message": str(e)}

# ---------------------------
# Data collector agent
# ---------------------------

system_prompt = """
        You are a data collection agent designed to gather information from new client inquiries.
        First, ask the client: "Is this a Family Inquiry or a Provider Referral?"

        Based on the user's response, use the appropriate tool:
        - If "Family Inquiry", call the 'get_inquiry_schema' tool to get the details needed.
        - If "Provider Referral", call the 'get_provider_schema' tool to get the details.

        Then, ask the client for the required details one field at a time as defined in the chosen schema.

        After collecting all responses, validate them with the client and, once confirmed, export the data as JSON using the appropriate store function (store_inquiry_data or store_provider_data).

        Once the data has been successfully exported:
        1. Remember the client_name that was collected
        2. Use check_session_state() to verify storage
        3. Ask the user if they want to ask some question or transfer to the email agent, keep asking this until user asks to transfer
        4. Transfer to the email agent with a simple context message
        5. Use: transfer_to_agent(agent_name='email_agent')

        After transferring to the email agent, the conversation is complete.
        """

data_agent = LlmAgent(
    name="data_collector_agent",
    model="gemini-2.0-flash",
    description="This agent collects client data in sequential pipeline either as Family Inquiry or Provider Referral. It uses tools to collect the information and store it in the json file",
    instruction=system_prompt,
    output_key="data_collection_status",  # This matches what email agent expects
    tools=[
        export_json_to_local,
        get_provider_schema,
        get_inquiry_schema,
        store_inquiry_data,
        store_provider_data,
        check_session_state
        #debug_session_state_before_and_after
        #get_or_create_session
        #generate_next_user_id,
        #check_existing_client
    ]
)

# Export the agent
__all__ = ['data_agent']