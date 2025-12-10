import asyncio
import logging
import os
from typing import Any

import google.generativeai as genai
from google.api_core import exceptions
from google.generativeai.types import HarmBlockThreshold, HarmCategory
from src.adk.core import Agent, AgentTool

logger = logging.getLogger(__name__)


class LlmAgent(Agent):
    """
    An agent backed by a Google Gemini LLM.
    """

    def __init__(
        self,
        name: str,
        model_name: str = "gemini-2.0-flash-exp",
        instructions: str = "",
        tools: list[AgentTool] | None = None,
        temperature: float = 0.7,
        max_retries: int = 3,
    ):
        super().__init__(name)
        self.model_name = model_name
        self.instructions = instructions
        self.tools = tools or []
        self.temperature = temperature
        self.max_retries = max_retries

        self._configure_genai()
        self.model = self._build_model()

    def _configure_genai(self):
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_API_KEY not found in environment.")
        else:
            genai.configure(api_key=api_key)

    def _build_model(self) -> genai.GenerativeModel:
        gemini_tools = [t.to_gemini_tool() for t in self.tools] if self.tools else None

        return genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.instructions,
            tools=gemini_tools,
            generation_config=genai.GenerationConfig(temperature=self.temperature),
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            },
        )

    async def run(self, input_data: Any, context: dict[str, Any]) -> str:
        logger.info(f"Agent {self.name} running with input: {str(input_data)[:50]}...")

        for attempt in range(self.max_retries + 1):
            try:
                if self.tools:
                    chat = self.model.start_chat(enable_automatic_function_calling=True)
                    response = await chat.send_message_async(str(input_data))
                else:
                    response = await self.model.generate_content_async(str(input_data))

                return response.text

            except exceptions.ResourceExhausted as e:
                if attempt < self.max_retries:
                    wait_time = (2**attempt) * 2
                    logger.warning(f"Agent {self.name} hit rate limit. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Agent {self.name} exhausted retries: {e}")
                    raise e
            except Exception as e:
                logger.error(f"Error in agent {self.name}: {e}")
                raise e
