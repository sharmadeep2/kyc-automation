"""Shared client factory for the Azure OpenAI Responses client."""

from __future__ import annotations

import os

from azure.identity import AzureCliCredential, DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()


def create_client():
    """Create and return an AzureOpenAIResponsesClient using env configuration."""
    from agent_framework.azure import AzureOpenAIResponsesClient

    endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
    deployment = os.environ["AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME"]

    try:
        credential = AzureCliCredential()
        # Quick check to verify the credential works
        credential.get_token("https://cognitiveservices.azure.com/.default")
    except Exception:
        credential = DefaultAzureCredential()

    return AzureOpenAIResponsesClient(
        azure_endpoint=endpoint,
        model=deployment,
        azure_credential=credential,
    )
