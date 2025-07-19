# main.py - Alternative Approach: Initialize Everything Here
"""
Alternative Multi-Agent Pipeline - Initialize in Main
====================================================

This approach initializes all session variables in main.py first,
then imports the agents to avoid context variable errors.
"""

import asyncio
import sys
import os
from pathlib import Path
import uuid
from datetime import datetime

# Add the current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# =============================================================================
# INITIALIZE SESSION FIRST
# =============================================================================

from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types

# Create session service and variables
session_service = InMemorySessionService()
SESSION_ID = str(uuid.uuid4())
USER_ID = datetime.now().strftime('%d%m%Y%H%M')
APP_NAME = "multi_agent_intake_system"

print(f"🔧 Initializing session variables...")
print(f"📋 Session ID: {SESSION_ID}")
print(f"👤 User ID: {USER_ID}")
print(f"📱 App Name: {APP_NAME}")

# Create session
session = session_service.create_session(
    session_id=SESSION_ID,
    user_id=USER_ID,
    app_name=APP_NAME,
)

print(f"✅ Session created successfully")

# =============================================================================
# NOW IMPORT AGENTS (after session is initialized)
# =============================================================================

# Set session variables in model.session_service module
import model.session_service as session_module
session_module.session_service = session_service
session_module.session = session
session_module.SESSION_ID = SESSION_ID
session_module.USER_ID = USER_ID
session_module.APP_NAME = APP_NAME

print(f"✅ Session variables set in session_service module")

# Now import your agents
try:
    from agent.root_agent.agent import root_agent
    print("✅ Successfully imported root_agent")
except ImportError as e:
    print(f"❌ Import error for root_agent: {e}")
    print("Make sure your agent files are in the correct structure")
    sys.exit(1)

# =============================================================================
# MAIN PIPELINE RUNNER
# =============================================================================

async def run_patient_intake_pipeline():
    """Run the complete patient intake pipeline using ADK AutoFlow."""
    
    print(f"\n🏥 Starting Patient Intake Pipeline")
    print(f"📋 Using session - User ID: {USER_ID}")
    print(f"🆔 Session ID: {SESSION_ID}")
    print(f"📱 App Name: {APP_NAME}")
    
    try:
        # Create runner using the session service
        runner = Runner(
            agent=root_agent,
            app_name=APP_NAME,
            session_service=session_service
        )
        
        print(f"\n🚀 Starting conversation with root agent...")
        
        # Start the conversation
        initial_message = types.Content(
            role='user',
            parts=[types.Part(text="Hello, I need help with patient intake")]
        )
        
        print(f"\n💬 You: Hello, I need help with patient intake")
        
        # Get initial response
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=initial_message
        ):
            if event.content and event.content.parts:
                response_text = event.content.parts[0].text
                print(f"🤖 Agent: {response_text}")
            
            if event.is_final_response():
                break
        
        # Interactive loop
        print(f"\n📝 Interactive Mode - Type your responses or 'quit' to exit")
        
        while True:
            try:
                user_input = input(f"\n💬 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'done']:
                    print("👋 Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                # Send user message
                message = types.Content(
                    role='user',
                    parts=[types.Part(text=user_input)]
                )
                
                # Get response
                async for event in runner.run_async(
                    user_id=USER_ID,
                    session_id=SESSION_ID,
                    new_message=message
                ):
                    if event.content and event.content.parts:
                        response_text = event.content.parts[0].text
                        print(f"🤖 Agent: {response_text}")
                    
                    if event.is_final_response():
                        break
                
                # Show session state updates (with error handling)
                try:
                    print(f"📊 Session state keys: {list(session.state.keys())}")
                except Exception as e:
                    print(f"⚠️ Could not access session state: {e}")
                
            except KeyboardInterrupt:
                print(f"\n👋 Exiting...")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                continue
        
        # Final status
        print(f"\n🎉 Pipeline session completed!")
        try:
            print(f"📋 Final session state keys: {list(session.state.keys())}")
            
            if session.state.get("data_collection_complete"):
                print("✅ Data collection: Complete")
            if session.state.get("email_sent"):
                print("✅ Email delivery: Complete")
        except Exception as e:
            print(f"⚠️ Could not check completion status: {e}")
            
    except Exception as e:
        print(f"❌ Pipeline error: {e}")
        import traceback
        traceback.print_exc()

# =============================================================================
# MAIN EXECUTION
# =============================================================================

async def main():
    """Main function."""
    print("🏥 Multi-Agent Patient Intake System")
    print("=====================================")
    
    try:
        await run_patient_intake_pipeline()
            
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Main error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Show initial state
    try:
        print(f"🔍 Initial session state: {list(session.state.keys())}")
    except Exception as e:
        print(f"⚠️ Could not show initial session state: {e}")
    
    # Run the main program
    asyncio.run(main())