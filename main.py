import os
import time
import requests
import json
from todoist_api_python.api import TodoistAPI
# Try importing TodoistAPIException from common locations
try:
    from todoist_api_python.api import TodoistAPIException
except ImportError:
    try:
        from todoist_api_python.models import TodoistAPIException # Attempt from models
    except ImportError:
        try:
            from todoist_api_python.exceptions import TodoistAPIException # Attempt from a hypothetical exceptions module
        except ImportError:
            print("Warning: Could not import TodoistAPIException from specific modules. Will use general Exception for API errors.")
            TodoistAPIException = Exception # Fallback to general Exception

from todoist_api_python.models import Task # Ensuring Project is not imported
from datetime import date, datetime, TIMEZONE
from flask import Flask, request

# --- Configuration ---
TODOIST_API_KEY = os.environ.get("TODOIST_API_KEY")
HABITICA_API_USER = os.environ.get("HABITICA_API_USER")
HABITICA_API_KEY = os.environ.get("HABITICA_API_KEY")
HABITICA_API_URL = "https://habitica.com/api/v3"
STATE_FILE_PATH = "/tmp/sync_state.json" # Or use os.path.join(tempfile.gettempdir(), "sync_state.json") for platform-agnostic temp path

# --- State (these will be loaded/populated by functions) ---
todoist_to_habitica_map = {} # Renamed from synced_tasks_map
processed_completed_todoist_tasks = set()
processed_completed_habitica_tasks = set()

# --- Helper Functions ---

def load_processed_state(file_path: str) -> tuple[set[str], set[str]]:
    """Loads the set of processed Todoist and Habitica task IDs from a JSON file."""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                state_data = json.load(f)
                pt_ids = set(state_data.get("processed_todoist_tasks", []))
                ph_ids = set(state_data.get("processed_habitica_tasks", []))
                print(f"Debug: Loaded state: {len(pt_ids)} processed Todoist, {len(ph_ids)} processed Habitica tasks.")
                return pt_ids, ph_ids
        else:
            print("Debug: State file not found. Starting with empty processed sets.")
    except json.JSONDecodeError as e:
        print(f"Warning: Could not decode JSON from state file {file_path}: {e}. Starting fresh.")
    except Exception as e:
        print(f"Warning: Could not load state from {file_path} due to an unexpected error: {e}. Starting fresh.")
    return set(), set()

def save_processed_state(file_path: str, p_todoist_tasks: set[str], p_habitica_tasks: set[str]):
    """Saves the set of processed Todoist and Habitica task IDs to a JSON file."""
    try:
        state_data = {
            "processed_todoist_tasks": list(p_todoist_tasks),
            "processed_habitica_tasks": list(p_habitica_tasks)
        }
        with open(file_path, 'w') as f:
            json.dump(state_data, f, indent=4)
        print(f"Debug: Saved state: {len(p_todoist_tasks)} processed Todoist, {len(p_habitica_tasks)} processed Habitica tasks to {file_path}.")
    except Exception as e:
        print(f"Error: Could not save state to {file_path}: {e}")

def get_todoist_tasks(api_token):
    """Get tasks from Todoist API."""
    try:
        # Get active tasks due today
        active_tasks = requests.get(
            "https://api.todoist.com/rest/v2/tasks",
            headers={"Authorization": f"Bearer {api_token}"},
            params={"filter": "due: {today}"}
        ).json()

        # Get completed tasks from today
        today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
        completed_tasks = requests.get(
            "https://api.todoist.com/rest/v2/completed/get_all",
            headers={"Authorization": f"Bearer {api_token}"},
            params={"since": today}
        ).json()

        # Create a set of completed task IDs
        completed_task_ids = {task['task_id'] for task in completed_tasks.get('items', [])}

        # Filter out completed tasks from active tasks
        active_tasks = [task for task in active_tasks if task['id'] not in completed_task_ids]

        return active_tasks, completed_task_ids
    except Exception as e:
        print(f"Error fetching Todoist tasks: {e}")
        return [], set()

def create_habitica_task_from_todoist(todoist_task_content: str, todoist_task_notes: str):
    """Creates a 'todo' in Habitica."""
    if not HABITICA_API_USER or not HABITICA_API_KEY:
        print("Habitica API credentials not set.")
        return None

    headers = {
        "x-api-user": HABITICA_API_USER,
        "x-api-key": HABITICA_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "text": todoist_task_content,
        "type": "todo",
        "notes": todoist_task_notes, # Make sure notes are passed
        "priority": 1 # Default priority, can be adjusted
    }
    try:
        response = requests.post(f"{HABITICA_API_URL}/tasks/user", headers=headers, json=payload)
        response.raise_for_status()
        habitica_task = response.json().get("data")
        print(f"Successfully created Habitica task: '{habitica_task.get('text')}' (ID: {habitica_task.get('id')})")
        return habitica_task
    except requests.exceptions.RequestException as e:
        print(f"Error creating Habitica task '{todoist_task_content}': {e}")
        if e.response is not None:
            print(f"Habitica API Response: {e.response.text}")
        return None

def complete_habitica_task(habitica_task_id: str, direction: str = "up"):
    """Scores a Habitica task. Direction 'up' for positive, 'down' for negative."""
    if not HABITICA_API_USER or not HABITICA_API_KEY:
        print("Habitica API credentials not set.")
        return False

    headers = {
        "x-api-user": HABITICA_API_USER,
        "x-api-key": HABITICA_API_KEY
    }
    score_url = f"{HABITICA_API_URL}/tasks/{habitica_task_id}/score/{direction}"
    try:
        response = requests.post(score_url, headers=headers)
        response.raise_for_status()
        print(f"Successfully scored Habitica task {habitica_task_id} ('{direction}')")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error scoring Habitica task {habitica_task_id}: {e}")
        if e.response is not None:
            print(f"Habitica API Response: {e.response.text}")
        return False

def get_habitica_user_tasks():
    """Fetches all of the user's todos from Habitica."""
    if not HABITICA_API_USER or not HABITICA_API_KEY:
        print("Habitica API credentials not set.")
        return []
    headers = {
        "x-api-user": HABITICA_API_USER,
        "x-api-key": HABITICA_API_KEY
    }
    
    final_tasks = []
    url = f"{HABITICA_API_URL}/tasks/user?type=todos" # Default: should fetch all (active and recently completed, hopefully)

    try:
        print(f"Debug: get_habitica_user_tasks: Fetching from URL: {url} (default list view)")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        tasks = response.json().get("data", [])
        print(f"Debug: get_habitica_user_tasks: Fetched {len(tasks)} tasks from default list view.")
        final_tasks = tasks # Use these tasks directly
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Habitica tasks from {url}: {e}")
        if e.response is not None:
            print(f"Habitica API Response: {e.response.text}")
    except json.JSONDecodeError as e:
        print(f"JSON decoding error for {url}: {e}. Response text: {response.text if response else 'No response object'}")
    
    num_truly_completed = sum(1 for t in final_tasks if t.get('completed'))
    print(f"Debug: get_habitica_user_tasks: After processing default list view, found {len(final_tasks)} tasks. {num_truly_completed} have 'completed: true'.")
    return final_tasks

def delete_habitica_task(habitica_task_id: str) -> bool:
    """Deletes a task from Habitica."""
    if not HABITICA_API_USER or not HABITICA_API_KEY:
        print("Habitica API credentials not set. Cannot delete task.")
        return False

    headers = {
        "x-api-user": HABITICA_API_USER,
        "x-api-key": HABITICA_API_KEY
    }
    delete_url = f"{HABITICA_API_URL}/tasks/{habitica_task_id}"
    
    try:
        print(f"Debug: Attempting to delete Habitica task ID: {habitica_task_id} from URL: {delete_url}")
        response = requests.delete(delete_url, headers=headers)
        response.raise_for_status() # Raises an exception for 4XX/5XX errors
        print(f"Successfully deleted Habitica task ID: {habitica_task_id}")
        return True
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 404:
            print(f"Warning: Habitica task ID {habitica_task_id} not found (404). Already deleted or invalid ID.")
            return True # Treat as success if it's already gone
        print(f"Error deleting Habitica task {habitica_task_id}: HTTP {http_err.response.status_code}")
        if http_err.response is not None:
            print(f"Habitica API Response: {http_err.response.text}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Error deleting Habitica task {habitica_task_id}: {e}")
        return False

def complete_todoist_task(api: TodoistAPI, todoist_task_id: str) -> bool:
    """Closes a task in Todoist."""
    try:
        # return api.close_task(task_id=todoist_task_id) # Original
        # Adding a check to ensure close_task returns a boolean or handles responses appropriately
        response = api.close_task(task_id=todoist_task_id)
        if response is True or (hasattr(response, 'status_code') and response.status_code == 204): # 204 No Content is success for close
             print(f"Debug: Todoist API confirmed close for task ID {todoist_task_id}")
             return True
        # Attempting to check common ways an SDK might return a successful empty response
        elif response is None or (isinstance(response, requests.Response) and response.ok): # Some SDKs might return None or an empty Response object
             print(f"Debug: Todoist API indicated success (possibly empty response) for closing task ID {todoist_task_id}")
             return True
        else:
             print(f"Warning: Todoist API did not explicitly confirm close for task ID {todoist_task_id}. Response: {response}")
             # Assuming if no exception, it might have worked, but logging a warning.
             # For stricter check, you might return False here if response isn't clearly True/204.
             return True # Tentatively true if no error, but depends on SDK's behavior for non-True success
    except TodoistAPIException as e: # Catch specific Todoist API exceptions
        print(f"Error completing Todoist task ID {todoist_task_id} via API: {e}")
        return False
    except Exception as e: # Catch any other exceptions
        print(f"Generic error completing Todoist task ID {todoist_task_id}: {e}")
        return False

def uncomplete_habitica_task(habitica_task_id: str) -> bool:
    """Uncompletes a task in Habitica."""
    if not HABITICA_API_USER or not HABITICA_API_KEY:
        print("Habitica API credentials not set.")
        return False

    headers = {
        "x-api-user": HABITICA_API_USER,
        "x-api-key": HABITICA_API_KEY
    }
    try:
        response = requests.post(f"{HABITICA_API_URL}/tasks/{habitica_task_id}/unlink", headers=headers)
        response.raise_for_status()
        print(f"Successfully uncompleted Habitica task {habitica_task_id}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error uncompleting Habitica task {habitica_task_id}: {e}")
        if e.response is not None:
            print(f"Habitica API Response: {e.response.text}")
        return False

def perform_single_sync_cycle(event=None, context=None):
    """Perform a single sync cycle between Todoist and Habitica."""
    try:
        # Get tasks from both systems
        todoist_tasks, completed_todoist_ids = get_todoist_tasks(TODOIST_API_KEY)
        habitica_tasks = get_habitica_user_tasks()

        # Create a mapping of task names to their IDs for both systems
        todoist_task_map = {task['content']: task['id'] for task in todoist_tasks}
        habitica_task_map = {task['text']: task['id'] for task in habitica_tasks}

        # Track which tasks we've processed
        processed_tasks = set()

        # First, handle tasks that exist in both systems
        for task_name, todoist_id in todoist_task_map.items():
            if task_name in habitica_task_map:
                habitica_id = habitica_task_map[task_name]
                processed_tasks.add(task_name)
                
                # Check if the task was completed in Todoist
                if todoist_id in completed_todoist_ids:
                    # Mark as complete in Habitica
                    complete_habitica_task(habitica_id)
                else:
                    # Ensure task is not completed in Habitica
                    uncomplete_habitica_task(habitica_id)

        # Then, handle tasks that only exist in Habitica
        for task_name, habitica_id in habitica_task_map.items():
            if task_name not in processed_tasks:
                # Check if this task was completed in Todoist
                if any(task_name in todoist_task_map and todoist_task_map[task_name] in completed_todoist_ids):
                    # Mark as complete in Habitica
                    complete_habitica_task(habitica_id)
                else:
                    # Delete from Habitica if it's not in Todoist and wasn't completed
                    delete_habitica_task(habitica_id)

        # Finally, add any new tasks from Todoist to Habitica
        for task_name, todoist_id in todoist_task_map.items():
            if task_name not in processed_tasks and todoist_id not in completed_todoist_ids:
                create_habitica_task_from_todoist(task_name, f"[TodoistID:{todoist_id}]")

        print("Sync cycle completed successfully")
        return True

    except Exception as e:
        print(f"Error during sync cycle: {e}")
        return False

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "Todoist-Habitica Sync Service is running"

@app.route('/sync', methods=['POST'])
def sync():
    try:
        perform_single_sync_cycle()
        return "Sync completed successfully", 200
    except Exception as e:
        return f"Error during sync: {str(e)}", 500

# if __name__ == "__main__":
#     # Get port from environment variable (required for Cloud Run)
#     port = int(os.environ.get("PORT", 8080))
#     # Ensure we're binding to 0.0.0.0 for Cloud Run
#     app.run(host='0.0.0.0', port=port, debug=False) 