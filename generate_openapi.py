import json
from fastapi.openapi.utils import get_openapi
from app.main import app
import os

def generate_spec():
    openapi_schema = get_openapi(
        title="Boce Unified Proxy Skill",
        version="1.0.0",
        description="A skill for checking URL availability and anomalies via Boce.",
        routes=app.routes,
    )
    
    # Save to file
    with open("openapi_skill.json", "w") as f:
        json.dump(openapi_schema, f, indent=2)
    print("✅ Generated openapi_skill.json")

if __name__ == "__main__":
    generate_spec()
