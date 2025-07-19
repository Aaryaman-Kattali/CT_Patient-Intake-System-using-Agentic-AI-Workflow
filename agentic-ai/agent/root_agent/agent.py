#root_agent
"""
Simplified Root Agent - Actually Works with ADK
===============================================


This version removes ALL the complex custom logic and uses ADK as designed.
Just 40 lines instead of 300+.
"""


from google.adk.agents import LlmAgent
from .subagents.data_collector_agent import data_agent
from .subagents.email_agent import email_agent
from .subagents.benefit_summary_agent import benefit_agent
from .subagents.soap_note_agent import soap_agent
#from model.session_service import session_service, SESSION_ID, USER_ID, APP_NAME


# Simple system prompt - just focus on the transfer logic
system_prompt = """
        You are a patient intake coordinator. Your job is simple:

        1. Greet new patients: "Welcome to our Patient Intake System! Are you here for Family Inquiry or Provider Referral services?"

        2. When they say "Provider Referral":
        - Say: "Perfect! Let me connect you with our data collection specialist."
        - Then call: transfer_to_agent(agent_name="data_collector_agent")

        3. When they say "Family Inquiry":
        - Say: "Great! Let me connect you with our family services team."
        - Then call: transfer_to_agent(agent_name="data_collector_agent")

        4. When email agent transfers the control back to you:
        - Ask: "Do you want the benefit summary or soap note?"
        - When they say "Benefit Summary":
        - Say: "Perfect! Let me connect you with our benefit summary agent."
        - Then call: transfer_to_agent(agent_name="benefit_summary_agent")
        - When they say "Soap Note":
        - Say: "Perfect! Let me connect you with our soap note agent."
        - Then call: transfer_to_agent(agent_name="soap_note_agent")

        5. When benefit summary agent transfers the control back to you:
        - Ask: "Do you want the soap note also?"
        - If yes, then call: transfer_to_agent(agent_name="soap_note_agent")
        - If no, then say "Thanks for using the application" and end the conversation

        6. When soap note agent transfers the control back to you:
        - Ask: "Do you want the benefit summary also?"
        - If yes, then call: transfer_to_agent(agent_name="benefit_summary_agent")
        - If no, then say "Thanks for using the application" and end the conversation
        
        That's it. ADK AutoFlow will handle the actual transfer automatically.
        """
#Session Info: Using session_id={SESSION_ID}, user_id={USER_ID}

# The entire root agent - this is all you need
root_agent = LlmAgent(
    name="root_patient_intake_agent",
    model="gemini-2.0-flash",
    description="Main patient intake coordinator",
    instruction=system_prompt,
    sub_agents=[data_agent, email_agent, benefit_agent, soap_agent]  # ADK AutoFlow handles everything else
)


# Export for other modules
__all__ = ['root_agent']
