# soap_note_agent
from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field
from typing import Optional
import json
import sys
import os
from datetime import datetime, date

# Add the model directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
# Navigate up to project root: soap_note_agent -> subagents -> root_agent -> agent -> project_root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
model_path = os.path.join(project_root, 'model')
if model_path not in sys.path:
    sys.path.insert(0, model_path)

# Import from the model directory
from model.soap_note import SOAPNote, create_synthetic_soap_note

class SOAPNoteRequest(BaseModel):
    """Request model for SOAP note generation"""
    user_input: str = Field(description="User's request for SOAP note generation")
    client_id: Optional[int] = Field(default=None, description="Client ID")
    client_first_name: Optional[str] = Field(default=None, description="Client first name")
    client_last_name: Optional[str] = Field(default=None, description="Client last name")
    birth_date: Optional[str] = Field(default=None, description="Birth date (YYYY-MM-DD)")
    created_by: Optional[str] = Field(default="System", description="Created by")
    num_notes: int = Field(default=1, description="Number of notes to generate")

def handle_soap_note_request(
    user_input: str,
    client_id: Optional[int] = None,
    client_first_name: Optional[str] = None,
    client_last_name: Optional[str] = None,
    birth_date: Optional[str] = None,
    created_by: str = "System",
    num_notes: int = 1
) -> str:
    """Generate SOAP notes based on user request"""
    try:
        generated_notes = []
        
        for i in range(num_notes):
            # Use provided data or generate defaults
            if client_id and client_first_name and client_last_name and birth_date:
                # Convert string date to date object
                birth_date_obj = datetime.strptime(birth_date, "%Y-%m-%d").date()
                
                # Create SOAP note with provided data
                soap_note = create_synthetic_soap_note(
                    client_id=client_id,
                    client_first_name=client_first_name,
                    client_last_name=client_last_name,
                    birth_date=birth_date_obj,
                    created_by=created_by
                )
            else:
                # Generate with synthetic data
                import random
                
                # Generate random client data
                first_names = ["John", "Jane", "Michael", "Sarah", "David", "Emily", "James", "Jessica"]
                last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]
                
                random_id = random.randint(10000, 99999)
                random_first = random.choice(first_names)
                random_last = random.choice(last_names)
                random_birth = date(random.randint(1950, 2005), random.randint(1, 12), random.randint(1, 28))
                
                soap_note = create_synthetic_soap_note(
                    client_id=random_id,
                    client_first_name=random_first,
                    client_last_name=random_last,
                    birth_date=random_birth,
                    created_by=created_by
                )
            
            # Convert to dictionary for JSON serialization
            note_dict = soap_note.model_dump()
            generated_notes.append(note_dict)
        
        # Return success response
        result = {
            'status': 'success',
            'message': f'Successfully generated {len(generated_notes)} SOAP note(s)',
            'soap_notes': generated_notes,
            'count': len(generated_notes)
        }
        
        return json.dumps(result, indent=2, default=str)
        
    except Exception as e:
        # Return error response
        result = {
            'status': 'error',
            'message': f'Error generating SOAP notes: {str(e)}',
            'soap_notes': [],
            'count': 0
        }
        return json.dumps(result, indent=2, default=str)

def generate_soap_notes_for_patient(
    client_id: int,
    client_first_name: str,
    client_last_name: str,
    birth_date: str,
    created_by: str = "System",
    num_notes: int = 3
) -> str:
    """Generate multiple SOAP notes for a specific patient"""
    return handle_soap_note_request(
        user_input=f"Generate {num_notes} SOAP notes for patient {client_first_name} {client_last_name}",
        client_id=client_id,
        client_first_name=client_first_name,
        client_last_name=client_last_name,
        birth_date=birth_date,
        created_by=created_by,
        num_notes=num_notes
    )

def generate_random_soap_notes(num_notes: int = 5) -> str:
    """Generate random SOAP notes with synthetic patient data"""
    return handle_soap_note_request(
        user_input=f"Generate {num_notes} random SOAP notes",
        num_notes=num_notes
    )

# System prompt for the agent
system_prompt = """
You are a SOAP note generation agent that creates comprehensive medical SOAP notes.

Available functions:
1. handle_soap_note_request() - Generate SOAP notes (general purpose)
2. generate_soap_notes_for_patient() - Generate multiple notes for a specific patient
3. generate_random_soap_notes() - Generate random notes with synthetic data

When generating SOAP notes:
- Use the create_synthetic_soap_note function from the model
- Generate realistic medical content for all SOAP components
- Include complete patient information and insurance details
- Return results in JSON format with clear status messages

Always provide helpful responses and handle errors gracefully.
"""

# Create the SOAP note agent
soap_agent = LlmAgent(
    name="soap_note_agent",
    model="gemini-2.0-flash",
    description="SOAP note generation agent for creating comprehensive medical notes",
    instruction=system_prompt,
    output_key="soap_note_result",
    tools=[handle_soap_note_request, generate_soap_notes_for_patient, generate_random_soap_notes]
)

# Export the agent
__all__ = ['soap_agent']