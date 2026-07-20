import json
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

# ==========================================
# 1. Configuration (Extracted from Images)
# ==========================================
ENDPOINT = "https://job-assignment-foundry-resource.services.ai.azure.com/api/projects/job-assignment-proj-default"

PARENT_AGENT_NAME = "Sales-opportunity-agent"
PARENT_AGENT_VERSION = "10" # Ensure this matches your latest published version

CHILD_AGENT_NAME = "Find-My-City"
CHILD_AGENT_VERSION = "5"

# ==========================================
# 2. Initialize Clients
# ==========================================
print("Authenticating and initializing Azure AI Project Client...")
project_client = AIProjectClient(
    endpoint=ENDPOINT,
    credential=DefaultAzureCredential(),
)
openai_client = project_client.get_openai_client()

# ==========================================
# 3. Define the Child Agent Execution Wrapper
# ==========================================
def call_find_my_city(usdot_number: str, legal_name: str = "") -> str:
    """Sends a request to the Find-My-City agent and returns its output."""
    prompt = f"Please resolve the physical City and State for USDOT Number: {usdot_number}. Legal Name: {legal_name}"
    
    response = openai_client.responses.create(
        input=[{"role": "user", "content": prompt}],
        extra_body={
            "agent_reference": {
                "name": CHILD_AGENT_NAME,
                "version": CHILD_AGENT_VERSION,
                "type": "agent_reference"
            }
        }
    )
    return response.output_text

# ==========================================
# 4. Define the Tool Schema for the Parent
# ==========================================
find_my_city_tool = {
    "type": "function",
    "function": {
        "name": "call_find_my_city",
        "description": "Enrich trucking company records by finding the physical City and State associated with a USDOT Number.",
        "parameters": {
            "type": "object",
            "properties": {
                "usdot_number": {"type": "string", "description": "The USDOT number of the trucking company."},
                "legal_name": {"type": "string", "description": "The optional legal name of the trucking company."}
            },
            "required": ["usdot_number"]
        }
    }
}

# ==========================================
# 5. Main Orchestration Loop
# ==========================================
def run_sales_orchestrator(user_query: str):
    print(f"\n--- New Inquiry: {user_query} ---\n")
    
    messages = [{"role": "user", "content": user_query}]
    
    print("[1] Executing Sales-opportunity-agent (Parent)...")
    
    # 5a. Initial call to Parent Agent. 
    # The parent has FMCSA_data_tool attached in the UI, and we inject find_my_city_tool here.
    response = openai_client.responses.create(
        input=messages,
        tools=[find_my_city_tool], 
        extra_body={
            "agent_reference": {
                "name": PARENT_AGENT_NAME,
                "version": PARENT_AGENT_VERSION,
                "type": "agent_reference"
            }
        }
    )
    
    # Check if the Parent Agent decided to call a tool
    # Note: Depending on the specific iteration of the Foundry API, tool_calls may live directly 
    # on the response or inside choices[0].message. Standardizing below:
    message_data = response.choices[0].message if hasattr(response, 'choices') else response
    
    if hasattr(message_data, 'tool_calls') and message_data.tool_calls:
        print("[2] Orchestrator requested tool execution.")
        messages.append(message_data) # Append the assistant's tool call state
        
        for tool_call in message_data.tool_calls:
            if tool_call.function.name == "call_find_my_city":
                args = json.loads(tool_call.function.arguments)
                print(f"    -> [Child Agent Triggered] Resolving location for USDOT: {args.get('usdot_number')}")
                
                # 5b. Execute Child Agent
                child_result = call_find_my_city(
                    usdot_number=args.get('usdot_number'),
                    legal_name=args.get('legal_name', '')
                )
                print(f"    -> [Child Agent Result]: {child_result}")
                
                # 5c. Append tool output back to the conversation thread
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": child_result
                })
        
        # 5d. Second round trip to Parent Agent to compile the final output script
        print("[3] Returning enriched geographic data back to Orchestrator...")
        final_response = openai_client.responses.create(
            input=messages,
            extra_body={
                "agent_reference": {
                    "name": PARENT_AGENT_NAME,
                    "version": PARENT_AGENT_VERSION,
                    "type": "agent_reference"
                }
            }
        )
        print(f"\n================ FINAL OUTPUT ================\n{final_response.output_text}")
    
    else:
        # If no tool was called (e.g., standard conversational reply)
        text_out = response.output_text if hasattr(response, 'output_text') else response.choices[0].message.content
        print(f"\n================ FINAL OUTPUT ================\n{text_out}")

# ==========================================
# 6. Test Execution
# ==========================================
if __name__ == "__main__":
    # Test query reflecting the core business requirement
    test_query = "Find carriers recently put out of service today. For each carrier, enrich the data with their city and state, then generate my personalized lead outreach script."
    run_sales_orchestrator(test_query)