
import httpx
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class EnhancedConvoTester:
    """Enhanced tester for multi-level convo testing."""
    
    def __init__(self, base_url: str = "http://localhost:4061"):
        self.base_url = base_url
        self.api_prefix = "/api/v1"
        self.token = None
        self.headers = {}
        
    async def login(self, email: str, password: str) -> bool:
        """Login and get authentication token."""
        url = f"{self.base_url}{self.api_prefix}/auth/login"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json={"email": email, "password": password},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.token = data.get("access_token")
                    self.headers = {"Authorization": f"Bearer {self.token}"}
                    print(f"✅ Logged in successfully as {email}")
                    return True
                else:
                    print(f"❌ Login failed: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return False
                    
            except Exception as e:
                print(f"❌ Login error: {e}")
                return False
    
    async def create_convo(self, convo_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new convo."""
        url = f"{self.base_url}{self.api_prefix}/convo/convos"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json=convo_data,
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 201:
                    data = response.json()
                    print(f"✅ Created convo: {data.get('id')}")
                    return data
                else:
                    print(f"❌ Failed to create convo: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return None
                    
            except Exception as e:
                print(f"❌ Error creating convo: {e}")
                return None
    
    async def start_chat(self, convo_id: str) -> Optional[Dict[str, Any]]:
        """Start a new chat session."""
        url = f"{self.base_url}{self.api_prefix}/convo/chat/start"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json={"convo_id": convo_id},
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    session_id = data.get('session_id')
                    print(f"✅ Started chat session: {session_id}")
                    print(f"🤖 Bot: {data.get('message')}")
                    
                    # Display options if available
                    if data.get('options'):
                        print("\n🔹 Available options:")
                        for idx, opt in enumerate(data.get('options', []), 1):
                            print(f"   {idx}. {opt.get('label')} (value: {opt.get('value')})")
                    
                    return data
                else:
                    print(f"❌ Failed to start chat: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return None
                    
            except Exception as e:
                print(f"❌ Error starting chat: {e}")
                return None
    
    async def send_message(self, session_id: str, message: str, display_options: bool = True) -> Optional[Dict[str, Any]]:
        """Send a message in a chat session."""
        url = f"{self.base_url}{self.api_prefix}/convo/chat/{session_id}/message"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    params={"message": message},  # Changed from json to params
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Sent message: '{message}'")
                    print(f"🤖 Bot: {data.get('message')}")
                    
                    # Display current state
                    print(f"   Node ID: {data.get('node_id')}")
                    print(f"   Node Type: {data.get('node_type')}")
                    print(f"   Expects Input: {data.get('expects_input')}")
                    
                    # Display options if available and requested
                    if display_options and data.get('options'):
                        print("\n🔹 Available options:")
                        for idx, opt in enumerate(data.get('options', []), 1):
                            print(f"   {idx}. {opt.get('label')} (value: {opt.get('value')})")
                    
                    return data
                else:
                    print(f"❌ Failed to send message: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return None
                    
            except Exception as e:
                print(f"❌ Error sending message: {e}")
                return None
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session details."""
        url = f"{self.base_url}{self.api_prefix}/convo/chat/{session_id}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"❌ Failed to get session: {response.status_code}")
                    return None
                    
            except Exception as e:
                print(f"❌ Error getting session: {e}")
                return None
    
    async def end_chat(self, session_id: str) -> bool:
        """End a chat session."""
        url = f"{self.base_url}{self.api_prefix}/convo/chat/{session_id}/end"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    print(f"✅ Ended chat session: {session_id}")
                    return True
                else:
                    print(f"❌ Failed to end chat: {response.status_code}")
                    return False
                    
            except Exception as e:
                print(f"❌ Error ending chat: {e}")
                return False
    
    async def delete_convo(self, convo_id: str) -> bool:
        """Delete a convo."""
        url = f"{self.base_url}{self.api_prefix}/convo/convos/{convo_id}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    url,
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    print(f"✅ Deleted convo: {convo_id}")
                    return True
                else:
                    print(f"❌ Failed to delete convo: {response.status_code}")
                    return False
                    
            except Exception as e:
                print(f"❌ Error deleting convo: {e}")
                return False


async def test_password_reset_flow(tester: EnhancedConvoTester, convo_id: str):
    """Test the password reset flow."""
    print("\n" + "="*80)
    print("TEST SCENARIO 1: Password Reset Flow")
    print("="*80)
    print("Path: Main Menu → Technical Support → Login Problems → Forgot Password → Provide Email")
    
    # Start chat
    print("\n📝 Starting chat session...")
    response = await tester.start_chat(convo_id)
    if not response:
        print("❌ Failed to start chat")
        return
    
    session_id = response.get("session_id")
    
    # Level 1: Select Technical Support
    print("\n" + "-"*80)
    print("LEVEL 1: Main Menu")
    print("-"*80)
    
    # Find the technical support option
    tech_support_value = None
    if response.get('options'):
        for opt in response.get('options', []):
            if 'technical' in opt.get('label', '').lower():
                tech_support_value = opt.get('value')
                break
    
    if not tech_support_value:
        print("❌ Could not find Technical Support option")
        return
    
    print(f"👤 User selects: Technical Support (value: {tech_support_value})")
    await asyncio.sleep(1)
    response = await tester.send_message(session_id, tech_support_value)
    
    if not response:
        return
    
    # Level 2: Select Login Problems
    print("\n" + "-"*80)
    print("LEVEL 2: Technical Support Menu")
    print("-"*80)
    
    # Find the login problems option
    login_problems_value = None
    if response.get('options'):
        for opt in response.get('options', []):
            if 'login' in opt.get('label', '').lower():
                login_problems_value = opt.get('value')
                break
    
    if not login_problems_value:
        print("❌ Could not find Login Problems option")
        return
    
    print(f"👤 User selects: Login Problems (value: {login_problems_value})")
    await asyncio.sleep(1)
    response = await tester.send_message(session_id, login_problems_value)
    
    if not response:
        return
    
    # Level 3: Select Forgot Password
    print("\n" + "-"*80)
    print("LEVEL 3: Login Issues Menu")
    print("-"*80)
    
    # Find the forgot password option
    forgot_password_value = None
    if response.get('options'):
        for opt in response.get('options', []):
            if 'forgot' in opt.get('label', '').lower() or 'password' in opt.get('label', '').lower():
                forgot_password_value = opt.get('value')
                break
    
    if not forgot_password_value:
        print("❌ Could not find Forgot Password option")
        return
    
    print(f"👤 User selects: Forgot Password (value: {forgot_password_value})")
    await asyncio.sleep(1)
    response = await tester.send_message(session_id, forgot_password_value)
    
    if not response:
        return
    
    # Level 4: Provide Email
    print("\n" + "-"*80)
    print("LEVEL 4: Email Collection")
    print("-"*80)
    
    if response.get('expects_input'):
        node_type = response.get('node_type')
        print(f"📝 Node type: {node_type}")
        print(f"   Expects input: {response.get('expects_input')}")
        print(f"   Input type: {response.get('input_type')}")
        print(f"   Input field: {response.get('input_field')}")
        
        # Provide email for password reset
        print("\n👤 User provides email: user@example.com")
        await asyncio.sleep(1)
        response = await tester.send_message(session_id, "user@example.com")
    else:
        print("⚠️  Node does not expect input, skipping email collection")
    
    if not response:
        return
    
    # Check if we need to navigate back or if the flow is complete
    print("\n" + "-"*80)
    print("Flow Status")
    print("-"*80)
    print(f"   Current node: {response.get('node_id')}")
    print(f"   Completed: {response.get('completed')}")
    print(f"   Has options: {len(response.get('options', []))} options")
    
    # If there are options to return to main menu, use them
    if response.get('options'):
        return_to_main_value = None
        for opt in response.get('options', []):
            if 'main' in opt.get('label', '').lower() or 'return' in opt.get('label', '').lower():
                return_to_main_value = opt.get('value')
                break
        
        if return_to_main_value:
            print(f"\n👤 User selects: Return to Main Menu")
            await asyncio.sleep(1)
            response = await tester.send_message(session_id, return_to_main_value)
    
    # Get session details
    print("\n📊 Retrieving session details...")
    await asyncio.sleep(1)
    session_details = await tester.get_session(session_id)
    
    if session_details:
        print("\n💬 Conversation Summary:")
        print(f"   Total messages: {len(session_details.get('history', []))}")
        print(f"   Current node: {session_details.get('current_node_id')}")
        print(f"   Context variables: {list(session_details.get('context', {}).keys())}")
        
        # Display context values
        if session_details.get('context'):
            print("\n📦 Context Values:")
            for key, value in session_details.get('context', {}).items():
                print(f"   {key}: {value}")
    
    # End chat
    print("\n🔚 Ending chat session...")
    await asyncio.sleep(1)
    await tester.end_chat(session_id)
    
    print("\n✅ Test completed successfully!")


async def test_account_unlock_flow(tester: EnhancedConvoTester, convo_id: str):
    """Test the account unlock flow (3 levels deep)."""
    print("\n" + "="*80)
    print("TEST SCENARIO 2: Account Unlock Flow (3 Levels Deep)")
    print("="*80)
    print("Path: Main Menu → Technical Support → Login Problems → Account Locked")
    
    # Start chat
    print("\n📝 Starting chat session...")
    response = await tester.start_chat(convo_id)
    if not response:
        print("❌ Failed to start chat")
        return
    
    session_id = response.get("session_id")
    
    # Level 1: Select Technical Support
    # Look for the actual option value from the response
    print("\n" + "-"*80)
    print("LEVEL 1: Main Menu")
    print("-"*80)
    
    # Find the technical support option
    tech_support_value = None
    if response.get('options'):
        for opt in response.get('options', []):
            if 'technical' in opt.get('label', '').lower():
                tech_support_value = opt.get('value')
                break
    
    if not tech_support_value:
        print("❌ Could not find Technical Support option")
        return
    
    print(f"👤 User selects: Technical Support (value: {tech_support_value})")
    await asyncio.sleep(1)
    response = await tester.send_message(session_id, tech_support_value)
    
    if not response:
        return
    
    # Level 2: Select Login Problems
    print("\n" + "-"*80)
    print("LEVEL 2: Technical Support Menu")
    print("-"*80)
    
    # Find the login problems option
    login_problems_value = None
    if response.get('options'):
        for opt in response.get('options', []):
            if 'login' in opt.get('label', '').lower():
                login_problems_value = opt.get('value')
                break
    
    if not login_problems_value:
        print("❌ Could not find Login Problems option")
        return
    
    print(f"👤 User selects: Login Problems (value: {login_problems_value})")
    await asyncio.sleep(1)
    response = await tester.send_message(session_id, login_problems_value)
    
    if not response:
        return
    
    # Level 3: Select Account Locked
    print("\n" + "-"*80)
    print("LEVEL 3: Login Issues Menu")
    print("-"*80)
    
    # Find the account locked option
    account_locked_value = None
    if response.get('options'):
        for opt in response.get('options', []):
            if 'account' in opt.get('label', '').lower() and 'lock' in opt.get('label', '').lower():
                account_locked_value = opt.get('value')
                break
    
    if not account_locked_value:
        print("❌ Could not find Account Locked option")
        return
    
    print(f"👤 User selects: Account Locked (value: {account_locked_value})")
    await asyncio.sleep(1)
    response = await tester.send_message(session_id, account_locked_value)
    
    if not response:
        return
    
    # Provide email for account unlock
    print("\n" + "-"*80)
    print("LEVEL 4: Email Collection")
    print("-"*80)
    print("👤 User provides email: user@example.com")
    await asyncio.sleep(1)
    response = await tester.send_message(session_id, "user@example.com")
    
    if not response:
        return
    
    # Return to main menu
    print("\n" + "-"*80)
    print("Navigation: Return to Main Menu")
    print("-"*80)
    
    # Find the return to main menu option
    return_to_main_value = None
    if response.get('options'):
        for opt in response.get('options', []):
            if 'main' in opt.get('label', '').lower() or 'return' in opt.get('label', '').lower():
                return_to_main_value = opt.get('value')
                break
    
    if not return_to_main_value:
        print("⚠️  Could not find Return to Main Menu option, using '1'")
        return_to_main_value = "1"
    
    print(f"👤 User selects: Return to Main Menu (value: {return_to_main_value})")
    await asyncio.sleep(1)
    response = await tester.send_message(session_id, return_to_main_value)
    
    # Get session details
    print("\n📊 Retrieving session details...")
    await asyncio.sleep(1)
    session_details = await tester.get_session(session_id)
    
    if session_details:
        print("\n💬 Conversation Summary:")
        print(f"   Total messages: {len(session_details.get('history', []))}")
        print(f"   Current node: {session_details.get('current_node_id')}")
        print(f"   Context variables: {list(session_details.get('context', {}).keys())}")
    
    # End chat
    print("\n🔚 Ending chat session...")
    await asyncio.sleep(1)
    await tester.end_chat(session_id)


async def main():
    """Main test runner."""
    # Initialize tester
    tester = EnhancedConvoTester("http://localhost:4061")
    
    # Login first
    print("🔐 Logging in...")
    if not await tester.login("chatbot@grucode.dev", "botchat@grucode.dev"):
        print("❌ Login failed, exiting...")
        return
    
    # Create test convos if needed
    # For demonstration, we'll assume convo IDs are known
    # In practice, you'd create these dynamically
    

    test_data_path = Path(__file__).parent.parent / "test_data" / "convos" / "simple_support_convo.json"
    
    with open(test_data_path, 'r') as f:
        convo_data = json.load(f)
    
    # Create convo
    convo = await tester.create_convo(convo_data)

    # Test password reset flow
    await test_password_reset_flow(tester, "simple_support_convo")
    
    # Test account unlock flow
    #await test_account_unlock_flow(tester, "enhanced_customer_support_flow")
    
    print("\n" + "="*80)
    print("🎉 All tests completed!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
