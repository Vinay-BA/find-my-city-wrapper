import os
print("========== MY APP.PY LOADED ==========")
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

load_dotenv()

app = FastAPI(
    title="Find My City Wrapper",
    version="1.0"
)

class FindCityRequest(BaseModel):
    usdot: str = Field(
        ..., 
        description="The US DOT Number of the trucking company (e.g., '123456'). Must be a string."
    )


# -----------------------------------------
# Azure AI Foundry configuration
# -----------------------------------------

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")

AGENT_NAME = os.getenv("AGENT_NAME")

AGENT_VERSION = os.getenv("AGENT_VERSION")


credential = DefaultAzureCredential()

project_client = AIProjectClient(
    endpoint=PROJECT_ENDPOINT,
    credential=credential,
)

openai_client = project_client.get_openai_client()


@app.get("/")
def root():
    return {"status": "Wrapper running"}


@app.post(
    "/find-city",
    summary="Find City and State by USDOT Number",
    description="Retrieves the physical city and state for a trucking company given their US DOT number. Call this tool when you need to enrich carrier data with location information.",
    operation_id="FindCityByUSDOT" # The parent agent will use this ID to call the tool
)
def find_city(request: FindCityRequest):

    prompt = f"""
Find the physical city and state for USDOT Number {request.usdot}.

Return ONLY JSON.

Example:

{{
    "city":"Dallas",
    "state":"Texas",
    "confidence":0.98
}}
"""

    try:

        response = openai_client.responses.create(

            input=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],

            extra_body={
                "agent_reference": {
                    "name": AGENT_NAME,
                    "version": AGENT_VERSION,
                    "type": "agent_reference",
                }
            },
        )

        return {
            "response": response.output_text
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
        