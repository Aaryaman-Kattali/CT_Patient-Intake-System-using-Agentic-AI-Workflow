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

class SOAPNoteRequest(BaseModel):
    """Simplified request model for SOAP note generation"""
    user_input: str = Field(description="User's request for SOAP note generation")
    use_synthetic_data: bool = Field(default=True, description="Whether to use synthetic data")

def safe_import_modules():
    """Safely import required modules"""
    try:
        from model.soap_note import SOAPNote, create_synthetic_soap_note, SOAPNoteTextGenerator
        return True, SOAPNote, create_synthetic_soap_note, SOAPNoteTextGenerator
    except Exception as e:
        return False, None, None, None

def handle_user_request(user_input: str, use_synthetic_data: bool = True) -> str:
    """
    Generate SOAP note and return the actual SOAP note text content
    
    Args:
        user_input: User's request for SOAP note generation
        use_synthetic_data: Whether to use synthetic data (default: True)
        
    Returns:
        The actual SOAP note text content (not debug info)
    """
    
    try:
        # Import modules
        import_success, SOAPNote, create_synthetic_soap_note, SOAPNoteTextGenerator = safe_import_modules()
        
        if not import_success:
            return "ERROR: Unable to import required modules for SOAP note generation."
        
        # Generate synthetic SOAP note
        try:
            import random
            
            # Generate random client data
            first_names = ["John", "Jane", "Michael", "Sarah", "David", "Emily", "James", "Jessica", "Christopher", "Ashley"]
            last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
            
            random_id = random.randint(10000, 99999)
            random_first = random.choice(first_names)
            random_last = random.choice(last_names)
            random_birth = date(random.randint(1950, 2005), random.randint(1, 12), random.randint(1, 28))
            
            soap_note = create_synthetic_soap_note(
                client_id=random_id,
                client_first_name=random_first,
                client_last_name=random_last,
                birth_date=random_birth,
                created_by="Dr. System"
            )
        except Exception as e:
            return f"ERROR: Failed to generate synthetic SOAP note data: {str(e)}"
        
        # Generate SOAP note text
        try:
            generator = SOAPNoteTextGenerator(soap_note)
            result = generator.get_soap_note_display()
            
            # Extract the actual SOAP note text from the result
            if isinstance(result, dict) and 'soap_note_text' in result:
                return result['soap_note_text']
            else:
                return "ERROR: SOAP note generation did not return expected format."
                
        except Exception as e:
            return f"ERROR: Failed to generate SOAP note text: {str(e)}"
        
    except Exception as e:
        return f"ERROR: Unexpected error in SOAP note generation: {str(e)}"

def handle_soap_note_request(
    user_input: str,
    client_id: Optional[int] = None,
    client_first_name: Optional[str] = None,
    client_last_name: Optional[str] = None,
    birth_date: Optional[str] = None,
    created_by: str = "System",
    num_notes: int = 1
) -> str:
    """Generate SOAP notes based on user request - legacy function for backwards compatibility"""
    try:
        import_success, SOAPNote, create_synthetic_soap_note, SOAPNoteTextGenerator = safe_import_modules()
        
        if not import_success:
            return json.dumps({
                'status': 'error',
                'message': 'Unable to import required modules',
                'soap_notes': [],
                'count': 0
            }, indent=2)
        
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

def debug_environment() -> str:
    """Debug the environment - only for troubleshooting"""
    try:
        import os
        import sys
        
        debug_info = []
        debug_info.append(f"Current working directory: {os.getcwd()}")
        debug_info.append(f"Python path includes model directory: {'model' in str(sys.path)}")
        
        # Check model directory
        model_dir = os.path.join(os.getcwd(), 'model')
        if os.path.exists(model_dir):
            model_files = os.listdir(model_dir)
            debug_info.append(f"Model directory files: {model_files}")
        else:
            debug_info.append("Model directory not found")
        
        # Test imports
        try:
            from model.soap_note import SOAPNote, create_synthetic_soap_note, SOAPNoteTextGenerator
            debug_info.append("✅ soap_note imports successful")
        except Exception as e:
            debug_info.append(f"❌ soap_note imports failed: {str(e)}")
        
        return "\n".join(debug_info)
        
    except Exception as e:
        return f"Debug environment check failed: {str(e)}"

# UPDATED system prompt that focuses on displaying the SOAP note content
system_prompt = """
You are a SOAP note generation agent that creates comprehensive medical SOAP notes.

Your workflow:
1. When a user requests a SOAP note, use the handle_user_request function
2. Display the complete SOAP note text directly to the user
3. Do NOT show debug information unless there's an error
4. After successfully showing the SOAP note, transfer back to the root agent

Instructions:
- Always use synthetic data by default
- Display the full SOAP note text in a clear, readable format
- Only show debug information if there are errors that need troubleshooting
- Keep responses focused on the SOAP note content, not the generation process

Response format for successful generation:
📋 **SOAP NOTE GENERATED**

[Display the complete SOAP note text here]

---
✅ SOAP note generated successfully. Transferring back to main menu...

Response format for errors:
❌ **ERROR GENERATING SOAP NOTE**

[Brief error description and any necessary debug info]

Available functions:
1. handle_user_request() - Generate SOAP note text (primary function)
2. handle_soap_note_request() - Generate SOAP notes in JSON format (legacy)
3. generate_soap_notes_for_patient() - Generate multiple notes for a specific patient
4. generate_random_soap_notes() - Generate random notes with synthetic data
5. debug_environment() - Debug environment issues

After displaying results (success or error), always call:
transfer_to_agent(agent_name='root_patient_intake_agent')
"""

# Create the SOAP note agent
soap_agent = LlmAgent(
    name="soap_note_agent",
    model="gemini-2.0-flash",
    description="Generates comprehensive medical SOAP notes with focus on displaying the actual note content",
    instruction=system_prompt,
    output_key="soap_note_result",
    tools=[handle_user_request, handle_soap_note_request, generate_soap_notes_for_patient, generate_random_soap_notes, debug_environment]
)

# Export the agent
__all__ = ['soap_agent']
