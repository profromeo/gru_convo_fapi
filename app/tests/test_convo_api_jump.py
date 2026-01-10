
import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import httpx

from app.core.services.convo_service import ConvoService
from app.core.models.convo import ChatSession, NodeAction, ApiAction, ConvoNode, NodeType

class TestConvoApiJump(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_settings = MagicMock()
        self.mock_db = AsyncMock()
        self.mock_auth_db = AsyncMock()
        self.service = ConvoService(self.mock_settings, self.mock_db, self.mock_auth_db)
        
        # Mock _update_session to avoid DB calls
        self.service._update_session = AsyncMock()
        self.service._find_value_in_nested_dict = MagicMock(return_value=(False, None))

    async def test_execute_api_action_success_jump(self):
        # Setup
        session = ChatSession(
            session_id="test_session",
            convo_id="test_convo",
            current_node_id="node1",
            context={},
            history=[]
        )
        
        api_config = ApiAction(
            url="http://test.com",
            method="GET",
            output=[]
        )
        
        action = NodeAction(
            type="api_call",
            api_action=api_config,
            on_success="success_node",
            on_failure="failure_node"
        )
        
        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "ok"}
        
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.return_value = mock_response
        mock_client.post.return_value = mock_response
        mock_client.put.return_value = mock_response
        mock_client.delete.return_value = mock_response
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            # Execute
            result = await self.service._execute_api_action(session, action)
            
            # Verify
            self.assertEqual(result, "success_node")
            
    async def test_execute_api_action_failure_jump(self):
        # Setup
        session = ChatSession(
            session_id="test_session",
            convo_id="test_convo",
            current_node_id="node1",
            context={},
            history=[]
        )
        
        api_config = ApiAction(
            url="http://test.com",
            method="GET",
            output=[]
        )
        
        action = NodeAction(
            type="api_call",
            api_action=api_config,
            on_success="success_node",
            on_failure="failure_node"
        )
        
        # Mock httpx.AsyncClient to raise error
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_request = MagicMock()
        
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        
        # Properly construct exception
        error = httpx.HTTPStatusError("Error", request=mock_request, response=mock_response)
        mock_client.get.side_effect = error
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            # Execute
            result = await self.service._execute_api_action(session, action)
            
            # Verify
            self.assertEqual(result, "failure_node")
            
    async def test_execute_node_actions_propagates_jump(self):
         # Setup
        session = ChatSession(
            session_id="test_session",
            convo_id="test_convo",
            current_node_id="node1",
            context={},
            history=[]
        )
        
        # Action that returns a jump
        action1 = NodeAction(type="api_call", api_action=ApiAction(url="x", method="GET"))
        
        node = ConvoNode(
            id="node1",
            name="Test Node",
            type=NodeType.MESSAGE,
            actions=[action1]
        )
        
        # Mock _execute_api_action to return "jump_target"
        self.service._execute_api_action = AsyncMock(return_value="jump_target")
        
        # Execute
        result = await self.service._execute_node_actions(session, node)
        
        # Verify
        self.assertEqual(result, "jump_target")
