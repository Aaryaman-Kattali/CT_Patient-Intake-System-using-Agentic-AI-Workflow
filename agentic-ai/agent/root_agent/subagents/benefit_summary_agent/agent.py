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

def debug_step(step_name: str, step_number: int, data=None):
    """Debug helper function to track execution steps"""
    print(f"\n🔍 DEBUG STEP {step_number}: {step_name}")
    print(f"   Status: EXECUTING")
    if data:
        print(f"   Data type: {type(data)}")
        if isinstance(data, dict):
            print(f"   Data keys: {list(data.keys())}")
    return True

def safe_import_modules():
    """Safely import required modules with debug info"""
    debug_results = {
        'benefit_check_summary': False,
        'benefit_check_form': False,
        'generate_benefit_summary_from_raw_data': False,
        'generate_synthetic_benefit_check_data': False
    }
    
    try:
        debug_step("Importing benefit_check_summary module", 1)
        from model.benefit_check_summary import generate_benefit_summary_from_raw_data
        debug_results['benefit_check_summary'] = True
        debug_results['generate_benefit_summary_from_raw_data'] = True
        print("   ✅ Successfully imported generate_benefit_summary_from_raw_data")
    except Exception as e:
        print(f"   ❌ Failed to import benefit_check_summary: {str(e)}")
        return debug_results, None, None
    
    try:
        debug_step("Importing benefit_check_form module", 2)
        from model.benefit_check_form import generate_synthetic_benefit_check_data
        debug_results['benefit_check_form'] = True
        debug_results['generate_synthetic_benefit_check_data'] = True
        print("   ✅ Successfully imported generate_synthetic_benefit_check_data")
    except Exception as e:
        print(f"   ❌ Failed to import benefit_check_form: {str(e)}")
        return debug_results, None, None
    
    return debug_results, generate_benefit_summary_from_raw_data, generate_synthetic_benefit_check_data

def handle_user_request(user_input: str, use_synthetic_data: bool = True) -> str:
    """
    SIMPLIFIED function for ADK compatibility
    
    Args:
        user_input: User's request for benefit summary
        use_synthetic_data: Whether to use synthetic data (default: True)
        
    Returns:
        JSON string with summary results and debug information
    """
    debug_info = []
    
    try:
        debug_info.append("Starting benefit summary generation")
        print("\n🚀 STARTING BENEFIT SUMMARY GENERATION")
        print("="*60)
        
        # Step 1: Process input
        debug_step("Processing request input", 1)
        debug_info.append(f"User input: {user_input}")
        debug_info.append(f"Use synthetic data: {use_synthetic_data}")
        print(f"   ✅ Request validation passed")
        
        # Step 2: Import modules
        debug_step("Importing required modules", 2)
        import_results, summary_func, synthetic_func = safe_import_modules()
        
        if not all([import_results['benefit_check_summary'], import_results['benefit_check_form']]):
            error_msg = f"Module import failed: {import_results}"
            debug_info.append(error_msg)
            result = {
                'status': 'error',
                'message': error_msg,
                'summary_text': '',
                'filename': '',
                'debug_info': debug_info
            }
            return json.dumps(result, indent=2, default=str)
        
        # Step 3: Generate synthetic data (always use synthetic for now)
        debug_step("Generating synthetic benefit check data", 3)
        debug_info.append("Using synthetic data")
        print("   📝 Generating synthetic benefit check data...")
        
        try:
            synthetic_form = synthetic_func()
            debug_info.append(f"Synthetic form type: {type(synthetic_form)}")
            print(f"   ✅ Synthetic form generated: {type(synthetic_form)}")
            
            # Convert to dictionary
            benefit_data = synthetic_form.model_dump()
            debug_info.append(f"Benefit data keys: {list(benefit_data.keys())}")
            print(f"   ✅ Converted to dict with {len(benefit_data)} keys")
            
        except Exception as e:
            error_msg = f"Failed to generate synthetic data: {str(e)}"
            debug_info.append(error_msg)
            debug_info.append(f"Traceback: {traceback.format_exc()}")
            result = {
                'status': 'error',
                'message': error_msg,
                'summary_text': '',
                'filename': '',
                'debug_info': debug_info
            }
            return json.dumps(result, indent=2, default=str)
        
        # Step 4: Generate summary
        debug_step("Generating benefit summary", 4, benefit_data)
        debug_info.append("Calling generate_benefit_summary_from_raw_data")
        
        try:
            result = summary_func(benefit_data)
            debug_info.append(f"Summary result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
            print(f"   ✅ Summary generated successfully")
            
            # Verify result structure
            if not isinstance(result, dict):
                error_msg = f"Summary function returned {type(result)}, expected dict"
                debug_info.append(error_msg)
                result = {
                    'status': 'error',
                    'message': error_msg,
                    'summary_text': '',
                    'filename': '',
                    'debug_info': debug_info
                }
                return json.dumps(result, indent=2, default=str)
            
        except Exception as e:
            error_msg = f"Failed to generate summary: {str(e)}"
            debug_info.append(error_msg)
            debug_info.append(f"Traceback: {traceback.format_exc()}")
            result = {
                'status': 'error',
                'message': error_msg,
                'summary_text': '',
                'filename': '',
                'debug_info': debug_info
            }
            return json.dumps(result, indent=2, default=str)
        
        # Step 5: Prepare final result
        debug_step("Preparing final result", 5)
        result['status'] = 'success'
        result['message'] = 'Benefit summary generated successfully'
        result['data_source'] = 'synthetic_data' if use_synthetic_data else 'provided_data'
        result['debug_info'] = debug_info
        
        print("   ✅ Final result prepared")
        print("="*60)
        print("🎉 BENEFIT SUMMARY GENERATION COMPLETED SUCCESSFULLY!")
        
        return json.dumps(result, indent=2, default=str)
        
    except Exception as e:
        error_msg = f"Unexpected error in handle_user_request: {str(e)}"
        debug_info.append(error_msg)
        debug_info.append(f"Full traceback: {traceback.format_exc()}")
        
        print(f"\n❌ CRITICAL ERROR: {error_msg}")
        print("="*60)
        
        result = {
            'status': 'error',
            'message': error_msg,
            'summary_text': '',
            'filename': '',
            'debug_info': debug_info
        }
        return json.dumps(result, indent=2, default=str)

def debug_environment() -> str:
    """Debug the environment and available modules - returns JSON string"""
    debug_info = []
    
    print("\n🔧 ENVIRONMENT DEBUG")
    print("="*40)
    
    # Check Python path
    import sys
    print(f"Python path: {sys.path}")
    debug_info.append(f"Python path: {sys.path}")
    
    # Check current working directory
    import os
    print(f"Current working directory: {os.getcwd()}")
    debug_info.append(f"Current working directory: {os.getcwd()}")
    
    # Check if model directory exists
    model_dir = os.path.join(os.getcwd(), 'model')
    print(f"Model directory exists: {os.path.exists(model_dir)}")
    debug_info.append(f"Model directory exists: {os.path.exists(model_dir)}")
    
    if os.path.exists(model_dir):
        model_files = os.listdir(model_dir)
        print(f"Model directory contents: {model_files}")
        debug_info.append(f"Model directory contents: {model_files}")
    
    # Try to import each module individually
    modules_to_test = [
        'model.benefit_check_summary',
        'model.benefit_check_form'
    ]
    
    for module_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"✅ Successfully imported {module_name}")
            debug_info.append(f"Successfully imported {module_name}")
        except Exception as e:
            print(f"❌ Failed to import {module_name}: {str(e)}")
            debug_info.append(f"Failed to import {module_name}: {str(e)}")
    
    return json.dumps({"debug_info": debug_info}, indent=2)

# SIMPLIFIED system prompt for ADK compatibility
system_prompt = """
You are a debug-enabled benefit summary agent that generates comprehensive insurance benefit summaries.

Your workflow:
1. When asked to generate a benefit summary, call handle_user_request with the user's request
2. Display the debug information and results clearly
3. If there are errors, show the debug information to help identify issues
4. After completing the task, transfer control back to the root agent

Available tools:
- handle_user_request(user_input, use_synthetic_data=True): Generate benefit summary
- debug_environment(): Debug the system environment

Instructions:
- Always use synthetic data by default
- Display results in a clear, organized format
- Show debug information to help troubleshoot issues
- After showing results, transfer back to root agent using transfer_to_agent(agent_name='root_patient_intake_agent')

Response format:
🔍 DEBUG INFORMATION:
[Show debug steps and system info]

📋 BENEFIT SUMMARY RESULT:
[Show the generated summary or error details]

🔄 NEXT STEPS:
[Indicate transfer back to root agent]
"""

# Create the simplified benefit summary agent
benefit_agent = LlmAgent(
    name="benefit_summary_agent",
    model="gemini-2.0-flash",
    description="Debug-enabled benefit summary agent that generates comprehensive benefit summaries with detailed debugging information",
    instruction=system_prompt,
    output_key="benefit_summary_result",
    tools=[handle_user_request, debug_environment]
)

# Export the agent
__all__ = ['benefit_agent']