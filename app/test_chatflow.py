
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class ConvoTester:
    """Test client for convo service."""
    
    def __init__(self, base_url: str = "http://localhost:4060", api_prefix: str = "/api/v1"):
        self.base_url = base_url
        self.api_prefix = api_prefix
        self.token: Optional[str] = None
        self.session_id: Optional[str] = None
        
    @property
    def headers(self) -> Dict[str, str]:
        """Get headers with authentication."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
    
    async def login(self, email: str, password: str) -> bool:
        """Login and get authentication token."""
        url = f"{self.base_url}{self.api_prefix}/auth/login"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json={"email": email, "password": password}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.token = data.get("access_token")
                    print(f"✅ Login successful for {email}")
                    return True
                else:
                    print(f"❌ Login failed: {response.status_code} - {response.text}")
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
    
    async def list_convos(self) -> Optional[list]:
        """List all convos."""
        url = f"{self.base_url}{self.api_prefix}/convo/convos"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Retrieved {len(data)} convos")
                    return data
                else:
                    print(f"❌ Failed to list convos: {response.status_code}")
                    return None
                    
            except Exception as e:
                print(f"❌ Error listing convos: {e}")
                return None
    
    async def get_convo(self, convo_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific convo."""
        url = f"{self.base_url}{self.api_prefix}/convo/convos/{convo_id}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Retrieved convo: {convo_id}")
                    return data
                else:
                    print(f"❌ Failed to get convo: {response.status_code}")
                    return None
                    
            except Exception as e:
                print(f"❌ Error getting convo: {e}")
                return None
    
    async def start_chat(self, convo_id: str, context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Start a new chat session."""
        url = f"{self.base_url}{self.api_prefix}/convo/chat/start"
        
        payload = {
            "convo_id": convo_id,
            "context": context or {}
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.session_id = data.get("session_id")
                    print(f"✅ Started chat session: {self.session_id}")
                    print(f"   Message: {data.get('message')}")
                    return data
                else:
                    print(f"❌ Failed to start chat: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return None
                    
            except Exception as e:
                print(f"❌ Error starting chat: {e}")
                return None
    
    async def send_message(self, session_id: str, message: str) -> Optional[Dict[str, Any]]:
        """Send a message in a chat session."""
        url = f"{self.base_url}{self.api_prefix}/convo/chat/{session_id}/message"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json={"message": message},
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Sent message: '{message}'")
                    print(f"   Response: {data.get('message')}")
                    return data
                else:
                    print(f"❌ Failed to send message: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return None
                    
            except Exception as e:
                print(f"❌ Error sending message: {e}")
                return None
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get chat session details."""
        url = f"{self.base_url}{self.api_prefix}/convo/chat/{session_id}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Retrieved session: {session_id}")
                    return data
                else:
                    print(f"❌ Failed to get session: {response.status_code}")
                    return None
                    
            except Exception as e:
                print(f"❌ Error getting session: {e}")
                return None
    
    async def end_chat(self, session_id: str) -> bool:
        """End a chat session."""
        url = f"{self.base_url}{self.api_prefix}/convo/chat/{session_id}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    url,
                    headers=self.headers,
                    timeout=30.0
                )
                
                if response.status_code == 204:
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
                
                if response.status_code == 204:
                    print(f"✅ Deleted convo: {convo_id}")
                    return True
                else:
                    print(f"❌ Failed to delete convo: {response.status_code}")
                    return False
                    
            except Exception as e:
                print(f"❌ Error deleting convo: {e}")
                return False


async def test_customer_support_flow(tester: ConvoTester):
    """Test the customer support flow."""
    print("\n" + "="*60)
    print("TEST: Customer Support Flow")
    print("="*60)
    
    # Load test data
    test_data_path = Path(__file__).parent.parent / "test_data" / "convos" / "customer_support_flow.json"
    
    with open(test_data_path, 'r') as f:
        convo_data = json.load(f)
    
    # Try to create convo (skip if already exists)
    convo = await tester.create_convo(convo_data)
    if not convo:
        print("ℹ️  Convo may already exist, continuing with test...")
    
    # Start chat
    print("\n📝 Starting chat session...")
    response = await tester.start_chat(convo_data["id"])
    if not response:
        print("❌ Failed to start chat")
        return
    
    session_id = response.get("session_id")
    
    # Display initial options
    if response.get("options"):
        print("\n🔹 Available options:")
        for idx, opt in enumerate(response.get("options", []), 1):
            print(f"   {idx}. {opt.get('label')}")
    
    # Select option 1 (Technical Issue)
    print("\n👤 User selects: 1 (Technical Issue)")
    await asyncio.sleep(1)
    response = await tester.send_message(session_id, "1")
    
    # Check if we moved to the correct node
    if response:
        print(f"\n🤖 Current node: {response.get('node_id')}")
        print(f"   Node type: {response.get('node_type')}")
        print(f"   Expects input: {response.get('expects_input')}")
        
        if response.get("options"):
            print("\n🔹 Available options:")
            for idx, opt in enumerate(response.get("options", []), 1):
                print(f"   {idx}. {opt.get('label')}")
    
    # Send technical issue description
    print("\n👤 User describes issue...")
    await asyncio.sleep(1)
    response = await tester.send_message(session_id, "My application keeps crashing when I try to save data")
    
    if response:
        print(f"\n🤖 Current node: {response.get('node_id')}")
        print(f"   Completed: {response.get('completed')}")
    
    # Get session details to see the full conversation
    print("\n📊 Retrieving session details...")
    await asyncio.sleep(1)
    session_details = await tester.get_session(session_id)
    
    if session_details:
        print("\n💬 Conversation History:")
        for msg in session_details.get("history", []):
            role = "👤 User" if msg.get("role") == "user" else "🤖 Bot"
            content = msg.get('content', '')[:100]  # Truncate long messages
            print(f"   {role}: {content}")
            print(f"      (Node: {msg.get('node_id')}, Time: {msg.get('timestamp')})")
        
        print("\n📦 Session Context:")
        for key, value in session_details.get("context", {}).items():
            print(f"   {key}: {value}")
    
    # End chat
    print("\n🔚 Ending chat session...")
    await asyncio.sleep(1)
    await tester.end_chat(session_id)
    
    # Clean up - delete convo
    #await asyncio.sleep(1)
    #await tester.delete_convo(convo_data["id"])


async def test_simple_greeting_flow(tester: ConvoTester):
    """Test the simple greeting flow."""
    print("\n" + "="*60)
    print("TEST: Simple Greeting Flow")
    print("="*60)
    
    # Load test data
    test_data_path = Path(__file__).parent.parent / "test_data" / "convos" / "simple_greeting_flow.json"
    
    with open(test_data_path, 'r') as f:
        convo_data = json.load(f)
    
    # Create convo
    convo = await tester.create_convo(convo_data)
    #if not convo:
    #    print("❌ Failed to create convo")
    #    return
    
    # Start chat
    print("\n📝 Starting chat session...")
    response = await tester.start_chat(convo_data["id"])
    if not response:
        print("❌ Failed to start chat")
        return
    
    session_id = response.get("session_id")
    
    # Send user's name
    print("\n👤 User provides name: John Doe")
    await asyncio.sleep(1)
    response = await tester.send_message(session_id, "John Doe")
    
    if response:
        print(f"\n🤖 Current node: {response.get('node_id')}")
        print(f"   Completed: {response.get('completed')}")
    
    # Get session details
    print("\n📊 Retrieving session details...")
    await asyncio.sleep(1)
    session_details = await tester.get_session(session_id)
    
    if session_details:
        print("\n💬 Conversation History:")
        for msg in session_details.get("history", []):
            role = "👤 User" if msg.get("role") == "user" else "🤖 Bot"
            print(f"   {role}: {msg.get('content')}")
    
    # End chat
    print("\n🔚 Ending chat session...")
    await asyncio.sleep(1)
    await tester.end_chat(session_id)
    
    # Clean up - delete convo
    await asyncio.sleep(1)
    await tester.delete_convo(convo_data["id"])


async def main():
    """Main test function."""
    # Initialize tester
    tester = ConvoTester()
    
    # Login first
    if not await tester.login("chatbot@grucode.dev", "botchat@grucode.dev"):
        print("❌ Login failed, exiting...")
        return
    
    # Run tests
    #await test_simple_greeting_flow(tester)
    await test_customer_support_flow(tester)
    
    print("\n" + "="*60)
    print("ALL TESTS COMPLETED")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
