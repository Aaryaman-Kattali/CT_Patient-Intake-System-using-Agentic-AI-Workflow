#benfit summary agent
from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Union
import json
import traceback
from datetime import date

class BenefitSummaryRequest(BaseModel):
    """Simplified request model for benefit summary generation"""
    user_input: str = Field(description="User's request for benefit summary")
    use_synthetic_data: bool = Field(default=True, description="Whether to use synthetic data")

def safe_import_modules():
    """Safely import required modules"""
    try:
        from model.benefit_check_summary import generate_benefit_summary_from_raw_data
        from model.benefit_check_form import generate_synthetic_benefit_check_data
        return True, generate_benefit_summary_from_raw_data, generate_synthetic_benefit_check_data
    except Exception as e:
        return False, None, None

def handle_user_request(user_input: str, use_synthetic_data: bool = True) -> str:
    """
    Generate benefit summary and return the actual summary text content
    
    Args:
        user_input: User's request for benefit summary
        use_synthetic_data: Whether to use synthetic data (default: True)
        
    Returns:
        The actual benefit summary text content (not debug info)
    """
    
    try:
        # Import modules
        import_success, summary_func, synthetic_func = safe_import_modules()
        
        if not import_success:
            return "ERROR: Unable to import required modules for benefit summary generation."
        
        # Generate synthetic data
        try:
            synthetic_form = synthetic_func()
            benefit_data = synthetic_form.model_dump()
        except Exception as e:
            return f"ERROR: Failed to generate synthetic benefit data: {str(e)}"
        
        # Generate summary
        try:
            result = summary_func(benefit_data)
            
            # Extract the actual summary text from the result
            if isinstance(result, dict) and 'summary_text' in result:
                return result['summary_text']
            else:
                return "ERROR: Summary generation did not return expected format."
                
        except Exception as e:
            return f"ERROR: Failed to generate benefit summary: {str(e)}"
        
    except Exception as e:
        return f"ERROR: Unexpected error in benefit summary generation: {str(e)}"

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
            from model.benefit_check_summary import generate_benefit_summary_from_raw_data
            debug_info.append("✅ benefit_check_summary import successful")
        except Exception as e:
            debug_info.append(f"❌ benefit_check_summary import failed: {str(e)}")
        
        try:
            from model.benefit_check_form import generate_synthetic_benefit_check_data
            debug_info.append("✅ benefit_check_form import successful")
        except Exception as e:
            debug_info.append(f"❌ benefit_check_form import failed: {str(e)}")
        
        return "\n".join(debug_info)
        
    except Exception as e:
        return f"Debug environment check failed: {str(e)}"

# UPDATED system prompt that focuses on displaying the benefit summary content
system_prompt = """
You are a benefit summary generation agent that creates comprehensive insurance benefit summaries.

Your workflow:
1. When a user requests a benefit summary, use the handle_user_request function
2. Display the complete benefit summary text directly to the user
3. Do NOT show debug information unless there's an error
4. After successfully showing the benefit summary, transfer back to the root agent

Instructions:
- Always use synthetic data by default
- Display the full benefit summary text in a clear, readable format
- Only show debug information if there are errors that need troubleshooting
- Keep responses focused on the benefit summary content, not the generation process

Response format for successful generation:
📋 **BENEFIT SUMMARY GENERATED**

[Display the complete benefit summary text here]

---
✅ Summary generated successfully. Transferring back to main menu...

Response format for errors:
❌ **ERROR GENERATING BENEFIT SUMMARY**

[Brief error description and any necessary debug info]

After displaying results (success or error), always call:
transfer_to_agent(agent_name='root_patient_intake_agent')
"""

# Create the benefit summary agent
benefit_agent = LlmAgent(
    name="benefit_summary_agent",
    model="gemini-2.0-flash",
    description="Generates comprehensive insurance benefit summaries with focus on displaying the actual summary content",
    instruction=system_prompt,
    output_key="benefit_summary_result",
    tools=[handle_user_request, debug_environment]
)

# Export the agent
__all__ = ['benefit_agent']
