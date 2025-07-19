#email_agent
import smtplib
import json
import os
import sys
import asyncio


from pathlib import Path
from typing import Literal, Optional
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.adk.agents import LlmAgent
#from agent.root_agent import root_agent


# Load environment from root_agent
env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=env_path)


# Add model directory for session service
from model.session_service import session_service, session, SESSION_ID, USER_ID, APP_NAME


# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
ORGANIZATION_NAME = os.getenv("ORGANIZATION_NAME", "Healthcare Services")


# SIMPLIFIED: Core email function that works with any data source
async def send_welcome_email_smart(
    session_id: Optional[str] = None,
    client_name: Optional[str] = None,
    client_email: Optional[str] = None,
    service_type: str = "inquiry"
) -> dict:
    """
    Smart email sender using the base session
    """
    
    print(f"🔍 DEBUG: Starting send_welcome_email_smart with session_id: {session_id}")
    
    # Get data from your base session
    try:
        from model.session_service import session
        
        print(f"📊 DEBUG: Full session state contents:")
        print(f"📊 DEBUG: {session.state}")
        
        client_data = session.state.get("client_data", {})
        
        if client_data:
            print(f"✅ DEBUG: Using SESSION DATA - Found client_data in session:")
            print(f"✅ DEBUG: Session client_data: {client_data}")
            
            client_name = client_name or client_data.get("client_name")
            client_email = client_email or client_data.get("client_email")
            
            # Detect service type from session data
            if "referral_type" in client_data:
                service_type = "provider referral"
            elif "relationship" in client_data:
                service_type = "family inquiry"
            
            print(f"📧 Found session data: {client_name}, {client_email}")
        else:
            print(f"❌ DEBUG: No client_data found in session state")
        
    except Exception as e:
        print(f"⚠️ Failed to read session state for email: {e}")

    # Fallback to latest local JSON if needed
    if not client_name or not client_email:
        print("🔄 DEBUG: FALLING BACK TO JSON FILES - Session data insufficient")
        print("📁 Falling back to local JSON files...")
        latest_data = get_latest_client_data()
        if latest_data["status"] == "success":
            print(f"✅ DEBUG: Using JSON DATA - Found data in file: {latest_data.get('file')}")
            print(f"✅ DEBUG: JSON client_data: {latest_data['data']}")
            
            client_name = client_name or latest_data["data"].get("client_name")
            client_email = client_email or latest_data["data"].get("client_email")
            if "referral_type" in latest_data["data"]:
                service_type = "provider referral"
            elif "relationship" in latest_data["data"]:
                service_type = "family inquiry"
        else:
            print(f"❌ DEBUG: JSON fallback also failed: {latest_data}")
            return {
                "status": "error",
                "message": "No valid client data found in session or local files"
            }
    else:
        print(f"✅ DEBUG: Successfully using SESSION DATA - no JSON fallback needed")

    # Final check
    if not client_name or not client_email:
        return {
            "status": "error",
            "message": f"Missing client_name ({client_name}) or client_email ({client_email}) after all attempts"
        }

    # Send email
    print(f"📧 Sending email to: {client_name} ({client_email}) using {service_type}")
    return send_email_core(client_name, client_email, service_type)

def debug_session_contents() -> dict:
    """
    Debug function to print and return current session contents
    """
    try:
        from model.session_service import session
        
        print(f"🔍 DEBUG SESSION CONTENTS:")
        print(f"Session ID: {session.id if hasattr(session, 'id') else 'N/A'}")
        print(f"Session State Keys: {list(session.state.keys())}")
        print(f"Full Session State: {session.state}")
        
        client_data = session.state.get("client_data", {})
        if client_data:
            print(f"Client Data Found: {client_data}")
        else:
            print("No client_data in session")
            
        return {
            "status": "success",
            "session_state": session.state,
            "client_data": client_data,
            "has_client_data": bool(client_data)
        }
        
    except Exception as e:
        print(f"Error accessing session: {e}")
        return {"status": "error", "message": f"Could not access session: {e}"}

def get_session_data() -> dict:
    """Get current session data for debugging."""
    try:
        return {
            "status": "success",
            "session_state": dict(session.state),
            "has_client_data": "client_data" in session.state,
            "ready_for_email": session.state.get("ready_for_email", False)
        }
    except Exception as e:
        return {"status": "error", "message": f"Session access failed: {e}"}

# ALSO ADD this helper function to email_agent.py
# async def get_session_data_for_email(session_id: str) -> dict:
#     """
#     Helper function to get session data specifically for email sending
#     """
#     try:
#         from model.session_service import session_service
       
#         # Try to get session by ID only first
#         sessions = await session_service.list_sessions(app_name="multi_agent_intake_system")
       
#         target_session = None
#         for session in sessions:
#             if session.id == session_id:
#                 target_session = session
#                 break
       
#         if not target_session:
#             return {"status": "error", "message": f"Session {session_id} not found"}
       
#         client_data = target_session.state.get("client_data", {})
       
#         return {
#             "status": "success",
#             "client_data": client_data,
#             "session_id": session_id,
#             "user_id": target_session.state.get("user_id")
#         }
       
#     except Exception as e:
#         return {"status": "error", "message": f"Error getting session data: {e}"}




def send_email_core(client_name: str, client_email: str, service_type: str) -> dict:
    """Core email sending logic."""
    try:
        if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
            return {"status": "error", "message": "Email credentials not configured"}
       
        # Determine email content
        if "referral" in service_type.lower():
            subject = f"Welcome to {ORGANIZATION_NAME} - Referral Received"
            service_text = "referral"
        else:
            subject = f"Welcome to {ORGANIZATION_NAME} - Inquiry Received"
            service_text = "inquiry"
       
        email_body = f"""Dear {client_name},


Welcome to our Patient Intake System!


We have received your {service_text} request and will process it shortly.


Our team will review your information and contact you within 1-2 business days with next steps.


If you have any urgent questions, please don't hesitate to contact us.


Best regards,
{ORGANIZATION_NAME} Team


---
This is an automated message. Please do not reply to this email.
        """.strip()
       
        # Create and send email
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = client_email
        msg['Subject'] = subject
        msg.attach(MIMEText(email_body, 'plain'))
       
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, client_email, msg.as_string())
        server.quit()
       
        return {
            "status": "success",
            "message": f"Welcome email sent successfully to {client_name} ({client_email})",
            "recipient": client_email,
            "subject": subject
        }
       
    except Exception as e:
        return {"status": "error", "message": f"Failed to send email: {str(e)}"}


def get_latest_client_data(directory: str = "collected_chatbot_data") -> dict:
    """Get the most recent client data from JSON files."""
    try:
        if not os.path.exists(directory):
            return {"status": "error", "message": f"Directory not found: {directory}"}
       
        json_files = [f for f in os.listdir(directory) if f.endswith('.json')]
        if not json_files:
            return {"status": "error", "message": "No client data files found"}
       
        # Get the most recent file
        full_paths = [os.path.join(directory, f) for f in json_files]
        latest_file = max(full_paths, key=os.path.getmtime)
       
        with open(latest_file, 'r') as f:
            data = json.load(f)
           
        return {"status": "success", "data": data, "file": latest_file}
       
    except Exception as e:
        return {"status": "error", "message": f"Error reading client data: {e}"}


def list_all_clients(directory: str = "collected_chatbot_data") -> dict:
    """List all client files for reference."""
    try:
        if not os.path.exists(directory):
            return {"status": "error", "message": f"Directory not found: {directory}"}
       
        files = [f for f in os.listdir(directory) if f.endswith(".json")]
        return {"status": "success", "files": files, "count": len(files)}
       
    except Exception as e:
        return {"status": "error", "message": f"Error listing files: {e}"}


# SIMPLIFIED: Email agent system prompt
system_prompt = """
        You are an email agent responsible for sending welcome emails to new clients.


        Your main task is to use the send_welcome_email_smart() tool to deliver the email


        Instructions:
        - When you take control, immediately call send_welcome_email_smart().
        - It will automatically:
            - Find the client data from the session state
            - Detect if it is a referral or inquiry
        - Customize welcome emails based on inquiry type (family inquiry vs provider referral)
        - Always confirm successful email delivery or report any errors
        - Ask user if they have any questions, if no then transfer control back to root agent
        - Keep asking if they have any question and answering until user asks to transfer
        - Use: transfer_to_agent(agent_name='root_agent')

        If send_welcome_email_smart() fails:
        - Use debug_session_contents() to inspect the session
        - Use list_all_clients() to view available records
        - Use get_latest_client_data() to inspect the most recent data

        The welcome emails are automatically customized based on whether the client data indicates a family inquiry or provider referral.

        Keep your responses short and focused. Only send the email and confirm the result.
        """


# FIXED: Email agent with simplified tools
email_agent = LlmAgent(
    name="email_agent",
    model="gemini-2.0-flash",
    description="Sends welcome emails automatically using the latest client data",
    instruction=system_prompt,
    output_key="email_delivery_status",
    tools=[
        send_welcome_email_smart,  # Main function
        get_latest_client_data,    # Backup data retrieval
        list_all_clients,          # Debug/reference
        send_email_core,            # Core email logic
        debug_session_contents,
        get_session_data
        #get_session_data_for_email
    ]
)

# Export the agent
__all__ = ['email_agent']