import requests
import json
import os # Import os to access environment variables

# Read credentials from environment variables
HABITICA_API_USER = os.environ.get("HABITICA_API_USER")
HABITICA_API_KEY = os.environ.get("HABITICA_API_KEY")
# Task ID from your logs for "H>T test"
HABITICA_TASK_ID = "05457321-a184-421c-bbba-fb408263d1b2"

HABITICA_API_URL = "https://habitica.com/api/v3"

def check_habitica_task_status():
    if not HABITICA_API_USER:
        print("Error: The HABITICA_API_USER environment variable is not set.")
        print("Please set it in your terminal session before running the script.")
        print("Example (PowerShell): $env:HABITICA_API_USER=\"your_habitica_user_id\"")
        print("Example (bash/zsh): export HABITICA_API_USER=\"your_habitica_user_id\"")
        return
    if not HABITICA_API_KEY:
        print("Error: The HABITICA_API_KEY environment variable is not set.")
        print("Please set it in your terminal session before running the script.")
        print("Example (PowerShell): $env:HABITICA_API_KEY=\"your_habitica_api_token\"")
        print("Example (bash/zsh): export HABITICA_API_KEY=\"your_habitica_api_token\"")
        return

    headers = {
        "x-api-user": HABITICA_API_USER,
        "x-api-key": HABITICA_API_KEY,
        "Content-Type": "application/json"
    }
    
    url = f"{HABITICA_API_URL}/tasks/{HABITICA_TASK_ID}"
    
    print(f"Requesting URL: {url}")
    print(f"Using API User ID (from env): {HABITICA_API_USER[:4]}... (masked for privacy)")
    # Avoid printing the API key directly, even masked, in routine logs unless necessary for deep debugging.
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        
        task_data = response.json()
        
        print("\\n--- Raw API Response ---")
        print(json.dumps(task_data, indent=2))
        
        print("\\n--- Key Information ---")
        task_details = task_data.get('data', {})
        print(f"Task ID: {task_details.get('id')}")
        print(f"Task Text: {task_details.get('text')}")
        print(f"Task Completed Status: {task_details.get('completed')}")
        
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {response.text}") # Use .text for better readability
    except requests.exceptions.RequestException as req_err:
        print(f"Request error occurred: {req_err}")
    except json.JSONDecodeError as json_err:
        print(f"JSON decoding error: {json_err}")
        print(f"Response content that failed to decode: {response.text}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    # Reminder of test steps:
    # 1. Ensure your HABITICA_API_USER and HABITICA_API_KEY environment variables are correctly set
    #    in the terminal session where you run this script.
    # 2. Ensure the Habitica task (ID: 05457321-a184-421c-bbba-fb408263d1b2)
    #    is marked as COMPLETE in the Habitica UI.
    # 3. Wait 1-2 minutes AFTER completing it in the UI.
    # 4. Then run this script: python check_habitica.py
    check_habitica_task_status() 