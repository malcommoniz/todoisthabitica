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

def get_todoist_tasks(api: TodoistAPI) -> list[Task]:
    """
    Fetches tasks from Todoist that are due today in EST timezone.
    Only returns tasks that are due today and not completed.
    """
    print("Debug: get_todoist_tasks: Initiating task fetch.")
    actual_tasks: list[Task] = []

    # Get today's date in EST timezone
    est_now = datetime.now(TIMEZONE)
    today = est_now.date().isoformat()
    print(f"Debug: Using EST date for filtering: {today}")

    try:
        print(f"Debug: get_todoist_tasks: Attempting fetch with filter='due: {today}'")
        tasks_response = api.get_tasks(filter=f"due: {today}")
        fetched_items = list(tasks_response) if tasks_response else []
        
        print(f"Debug: get_todoist_tasks: Received {len(fetched_items)} raw items from API.")

        for item in fetched_items:
            if isinstance(item, Task):
                # Only include tasks that are not completed
                if not item.is_completed:
                    actual_tasks.append(item)
            elif isinstance(item, list):
                for inner_item in item:
                    if isinstance(inner_item, Task) and not inner_item.is_completed:
                        actual_tasks.append(inner_item)

    except Exception as e:
        print(f"Error fetching tasks from Todoist: {e}")
        return []

    print(f"Debug: get_todoist_tasks: Returning {len(actual_tasks)} active tasks due today.")
    return actual_tasks

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

def perform_single_sync_cycle(event=None, context=None):
    """Performs one complete synchronization cycle from Todoist to Habitica and back."""
    
    # Initialize or load state
    global todoist_to_habitica_map
    todoist_to_habitica_map = {} 
    processed_completed_todoist_tasks, processed_completed_habitica_tasks = load_processed_state(STATE_FILE_PATH)

    if not TODOIST_API_KEY:
        print("Todoist API key not set. Please set the TODOIST_API_KEY environment variable.")
        return
    if not HABITICA_API_USER or not HABITICA_API_KEY:
        print("Habitica API User or Key not set. Please set them as environment variables.")
        return

    todoist_api = TodoistAPI(TODOIST_API_KEY)

    print("Starting Todoist-Habitica single sync cycle...")
    
    # Get today's date in EST timezone
    est_now = datetime.now(TIMEZONE)
    today_date = est_now.date()
    today_date_str = today_date.isoformat()
    print(f"Filtering for tasks due on: {today_date_str} (EST)")

    # 1. FETCH DATA
    todoist_tasks_for_today = get_todoist_tasks(todoist_api)
    todoist_tasks_by_id_map = {task.id: task for task in todoist_tasks_for_today if isinstance(task, Task)}

    print(f"Found {len(todoist_tasks_for_today)} active Todoist tasks due today.")
    active_todoist_ids_today = {t.id for t in todoist_tasks_for_today}

    habitica_tasks = get_habitica_user_tasks()

    # Check for and remove duplicate tasks
    remove_duplicate_habitica_tasks(habitica_tasks)

    # Add cleanup step for non-today tasks
    cleanup_non_today_habitica_tasks(habitica_tasks, todoist_tasks_for_today)

    # 2. RECONCILE todoist_to_habitica_map WITH HABITICA TAGS
    habitica_ids_with_valid_tags = set()
    for ht in habitica_tasks:
        if ht.get('type') == 'todo' and ht.get('notes') and '[TodoistID:' in ht['notes']:
            try:
                found_tid = ht['notes'].split('[TodoistID:')[1].split(']')[0]
                found_hid = ht['id']
                if found_tid:
                    habitica_ids_with_valid_tags.add(found_hid)
                    if found_tid not in todoist_to_habitica_map:
                        todoist_to_habitica_map[found_tid] = found_hid
                    elif todoist_to_habitica_map[found_tid] != found_hid:
                        print(f"Warning MAP-RECONCILE: Mismatch for Todoist ID {found_tid}. Map had H:{todoist_to_habitica_map[found_tid]}, Habitica tag has H:{found_hid}. Updating map to Habitica tag's version.")
                        todoist_to_habitica_map[found_tid] = found_hid
            except IndexError:
                print(f"Warning MAP-RECONCILE: Could not parse Todoist ID from Habitica task notes: {ht.get('text')}")

    # --- Combined T->H Sync: Process mapped tasks for completion, rescheduling, or deletion --- 
    ids_to_remove_from_map_after_combined_TH_sync = set()
    for todoist_id, habitica_id in list(todoist_to_habitica_map.items()):
        current_todoist_task_obj = todoist_tasks_by_id_map.get(todoist_id)
        if current_todoist_task_obj:
            if current_todoist_task_obj.is_completed:
                if todoist_id not in processed_completed_todoist_tasks:
                    print(f"Debug T->H SYNC: Todoist task '{current_todoist_task_obj.content[:30]}' (TID:{todoist_id}) is COMPLETED. Completing H:{habitica_id}.")
                    if complete_habitica_task(habitica_id):
                        processed_completed_todoist_tasks.add(todoist_id)
                        processed_completed_habitica_tasks.add(habitica_id)
                    else:
                        print(f"Failed to complete Habitica task {habitica_id} for T->H sync of TID:{todoist_id}")
                    ids_to_remove_from_map_after_combined_TH_sync.add(todoist_id)
            else:
                is_task_still_due_today = todoist_id in active_todoist_ids_today
                if not is_task_still_due_today:
                    print(f"Debug T->H SYNC: Todoist task '{current_todoist_task_obj.content[:30]}' (TID:{todoist_id}) is not due today. Deleting H:{habitica_id}.")
                    if delete_habitica_task(habitica_id):
                        pass
                    else:
                        print(f"Failed to delete stale Habitica task {habitica_id} for TID:{todoist_id}")
                    ids_to_remove_from_map_after_combined_TH_sync.add(todoist_id)
        else:
            if todoist_id not in processed_completed_todoist_tasks:
                print(f"Debug T->H SYNC: Todoist task (TID:{todoist_id}) from map not in API results (e.g. deleted/very old). Deleting H:{habitica_id}.")
                if delete_habitica_task(habitica_id): 
                    pass
                else:
                    print(f"Failed to delete Habitica task {habitica_id} for disappeared TID:{todoist_id}")
                ids_to_remove_from_map_after_combined_TH_sync.add(todoist_id)
    for tid_to_remove in ids_to_remove_from_map_after_combined_TH_sync:
        if tid_to_remove in todoist_to_habitica_map:
            del todoist_to_habitica_map[tid_to_remove]

    # 4. SYNC COMPLETIONS: HABITICA -> TODOIST
    ids_to_remove_from_map_after_H_T_sync = set()
    for h_task in habitica_tasks:
        h_id = h_task['id']
        h_text = h_task.get('text', 'Unknown Habitica Task')[:50]
        is_linked_via_tag = h_id in habitica_ids_with_valid_tags
        is_in_current_map_values = h_id in todoist_to_habitica_map.values()
        if (is_linked_via_tag or is_in_current_map_values) and h_task.get('completed') and h_id not in processed_completed_habitica_tasks:
            corresponding_tid = None
            for t_id, mapped_h_id in todoist_to_habitica_map.items():
                if mapped_h_id == h_id:
                    corresponding_tid = t_id
                    break
            if not corresponding_tid: 
                if '[TodoistID:' in h_task.get('notes', ''):
                    try:
                        corresponding_tid = h_task['notes'].split('[TodoistID:')[1].split(']')[0]
                    except IndexError:
                        pass
            if corresponding_tid and corresponding_tid not in processed_completed_todoist_tasks:
                print(f"Debug H->T COMPLETION: Habitica task '{h_text}...' (ID: {h_id}) is API_Completed: True. Corresponding Todoist ID: {corresponding_tid}.")
                print(f"Attempting to complete Todoist task {corresponding_tid}...")
                if complete_todoist_task(todoist_api, corresponding_tid):
                    print(f"Successfully completed Todoist task {corresponding_tid}.")
                    processed_completed_habitica_tasks.add(h_id)
                    processed_completed_todoist_tasks.add(corresponding_tid)
                    ids_to_remove_from_map_after_H_T_sync.add(corresponding_tid)
                else:
                    print(f"Failed to complete Todoist task {corresponding_tid}.")
            elif corresponding_tid and corresponding_tid in processed_completed_todoist_tasks:
                processed_completed_habitica_tasks.add(h_id) 
            elif not corresponding_tid:
                 print(f"Debug H->T COMPLETION: Habitica task '{h_text}...' (ID: {h_id}) is API_Completed: True, but could not find its corresponding Todoist ID in map or notes. Marking as processed to avoid loops.")
                 processed_completed_habitica_tasks.add(h_id)
    for tid_to_remove in ids_to_remove_from_map_after_H_T_sync:
        if tid_to_remove in todoist_to_habitica_map: 
            del todoist_to_habitica_map[tid_to_remove]

    # 5. SYNC NEW TASKS: TODOIST -> HABITICA
    for task in todoist_tasks_for_today: 
        if task.id not in todoist_to_habitica_map and not task.is_completed: 
            print(f"New uncompleted Todoist task due today: '{task.content[:50]}...'. Creating in Habitica...")
            habitica_notes = f"{task.description if task.description else ''}\n\n[TodoistID:{task.id}]"
            created_habitica_task = create_habitica_task_from_todoist(task.content, habitica_notes)
            if created_habitica_task and created_habitica_task.get('id'):
                new_hid = created_habitica_task['id']
                todoist_to_habitica_map[task.id] = new_hid
                print(f"Successfully created Habitica task for Todoist task '{task.content[:50]}...'. Mapped Todoist ID {task.id} to Habitica ID {new_hid}.")
            else:
                print(f"Failed to create Habitica task for Todoist task '{task.content[:50]}...'. Response: {created_habitica_task}")

    print(f"Current todoist_to_habitica_map size at end of cycle: {len(todoist_to_habitica_map)}")
    print(f"Processed Todoist completions cache size: {len(processed_completed_todoist_tasks)}")
    print(f"Processed Habitica completions cache size: {len(processed_completed_habitica_tasks)}")

    # Save the state at the end of the cycle
    save_processed_state(STATE_FILE_PATH, processed_completed_todoist_tasks, processed_completed_habitica_tasks)
    print("Todoist-Habitica single sync cycle finished.")
    return "Sync complete", 200


if __name__ == "__main__":
    # This script is now designed to be called by a scheduler.
    # When run directly, it will perform one sync cycle.
    
    # For Google Cloud Functions, the entry point will be perform_single_sync_cycle(event, context)
    # For local testing:
    perform_single_sync_cycle() 