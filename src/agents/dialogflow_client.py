"""
Dialogflow CX Client Wrapper

Handles authentication and session management for the Dialogflow CX agent.
"""

import os
from typing import Optional

from google.api_core.client_options import ClientOptions
from google.cloud.dialogflowcx_v3.services.sessions import SessionsClient
from google.cloud.dialogflowcx_v3.types import DetectIntentRequest, QueryInput, TextInput


class DialogflowClient:
    """Wrapper for Dialogflow CX interactions."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        location_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ):
        self.project_id = project_id or os.getenv("DIALOGFLOW_PROJECT_ID")
        self.location_id = location_id or os.getenv("DIALOGFLOW_LOCATION", "global")
        self.agent_id = agent_id or os.getenv("DIALOGFLOW_AGENT_ID")

        if not all([self.project_id, self.location_id, self.agent_id]):
            raise ValueError(
                "Missing Dialogflow configuration. "
                "Ensure DIALOGFLOW_PROJECT_ID, DIALOGFLOW_LOCATION, and DIALOGFLOW_AGENT_ID are set."
            )

        client_options = None
        if self.location_id != "global":
            api_endpoint = f"{self.location_id}-dialogflow.googleapis.com:443"
            client_options = ClientOptions(api_endpoint=api_endpoint)

        self.client = SessionsClient(client_options=client_options)

    def detect_intent(self, session_id: str, text: str, language_code: str = "en") -> str:
        """
        Send a text message to the agent and receive a response.

        Args:
            session_id: Unique session identifier (e.g., user ID or UUID).
            text: The user's input message.
            language_code: Language code for the request.

        Returns:
            The agent's text response.
        """
        session_path = self.client.session_path(
            project=self.project_id,
            location=self.location_id,
            agent=self.agent_id,
            session=session_id,
        )

        text_input = TextInput(text=text)
        query_input = QueryInput(text=text_input, language_code=language_code)

        request = DetectIntentRequest(
            session=session_path,
            query_input=query_input,
        )

        response = self.client.detect_intent(request=request)

        # Extract the text response
        response_messages = response.query_result.response_messages
        response_text = ""

        for message in response_messages:
            if message.text:
                response_text += "".join(message.text.text) + "\n"

        return response_text.strip()
