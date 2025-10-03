import requests
import json

# Paste your Google API Key here.
# API_KEY = "AIzaSyCLM9lAFMh4_3aAfZgSpJi07UCrORj0vDw"

# Google 2.5 pro or 1.5 pro key
API_KEY="AIzaSyCKnigoTJud59eYZu5XC5Lr5kypyMQYT6s"

# This is the endpoint to list available models.
URL = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"

print("--- Requesting list of available models... ---")

try:
    response = requests.get(URL)
    response.raise_for_status() # Raise an error for bad status codes

    print("--- ✅ SUCCESS ---")
    data = response.json()
    
    # Print the name of each model found
    for model in data.get("models", []):
        print(f"  - {model.get('name')}")

except requests.exceptions.HTTPError as http_err:
    print(f"\n--- ❌ HTTP ERROR OCCURRED ---")
    print(f"Status Code: {http_err.response.status_code}")
    print("Error Response from Server:")
    print(json.dumps(http_err.response.json(), indent=2))
except Exception as err:
    print(f"\n--- ❌ AN UNEXPECTED ERROR OCCURRED ---")
    print(err)