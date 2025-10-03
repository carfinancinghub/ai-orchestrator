import requests
import json

# --- Configuration ---------------------------------------------------------
# 1. Paste your Google API Key directly here between the quotes.
API_KEY = "GOOGLE_API_KEY_DEMO"

# 2. We will use the known-good model and URL structure.
MODEL_NAME = "gemini-pro-latest"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"
# ---------------------------------------------------------------------------

# Define the headers for the request
headers = {
    "Content-Type": "application/json"
}

# Create the request body with the correct structure
body = {
    "contents": [{
        "role": "user",
        "parts": [{
            "text": "This is a simple test. If you see this, respond with only the words 'Test successful!'"
        }]
    }]
}

# --- Main execution --------------------------------------------------------
def run_test():
    """Sends a single request to the Gemini API and prints the result."""
    print("--- Sending request to Gemini API... ---")
    print(f"URL: {URL.split('?')[0]}?key=AIza...[REDACTED]") # Print URL without leaking key
    print(f"BODY: {json.dumps(body, indent=2)}")

    try:
        # Send the POST request
        response = requests.post(URL, headers=headers, json=body)

        # This line will raise an error for any bad status codes (4xx or 5xx)
        response.raise_for_status()

        # If we get here, the request was successful (2xx status code)
        print("\n--- ✅ REQUEST SUCCESSFUL ---")
        print("Response JSON:")
        # Pretty-print the JSON response from the API
        print(json.dumps(response.json(), indent=2))

    except requests.exceptions.HTTPError as http_err:
        # This block catches specific HTTP errors (like 400, 404, 500)
        print(f"\n--- ❌ HTTP ERROR OCCURRED ---")
        print(f"Status Code: {http_err.response.status_code}")
        print("Error Response from Server:")
        try:
            # Try to pretty-print the JSON error response
            print(json.dumps(http_err.response.json(), indent=2))
        except json.JSONDecodeError:
            # If the error response isn't JSON, print it as raw text
            print(http_err.response.text)

    except Exception as err:
        # This block catches other errors (like network connection issues)
        print(f"\n--- ❌ AN UNEXPECTED ERROR OCCURRED ---")
        print(err)

if __name__ == "__main__":
    run_test()