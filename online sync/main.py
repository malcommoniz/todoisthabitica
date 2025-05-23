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
from datetime import date, datetime
import pytz  # Add pytz for timezone handling

# --- Configuration ---
TODOIST_API_KEY = os.environ.get("TODOIST_API_KEY")
HABITICA_API_USER = os.environ.get("HABITICA_API_USER")
HABITICA_API_KEY = os.environ.get("HABITICA_API_KEY")
HABITICA_API_URL = "https://habitica.com/api/v3"
STATE_FILE_PATH = "/tmp/sync_state.json" # Or use os.path.join(tempfile.gettempdir(), "sync_state.json") for platform-agnostic temp path
TIMEZONE = pytz.timezone('America/New_York')  # Set timezone to EST

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
    Attempts to get tasks due today using a filter if supported.
    Falls back to fetching all tasks if the filter fails or yields no results.
    Correctly processes items if they are lists containing Task objects.
    """
    print("Debug: get_todoist_tasks: Initiating task fetch.")
    actual_tasks: list[Task] = []

    # Get today's date in EST timezone
    est_now = datetime.now(TIMEZONE)
    today = est_now.date().isoformat()
    print(f"Debug: Using EST date for filtering: {today}")

    # Attempt 1: Use the filter for exact date match
    try:
        print(f"Debug: get_todoist_tasks: Attempting fetch with filter='due: {today}'")
        tasks_response = api.get_tasks(filter=f"due: {today}")
        fetched_items = list(tasks_response) if tasks_response else []
        
        print(f"Debug: get_todoist_tasks (filter attempt): Received {len(fetched_items)} raw items from API.")

        for item_index, item in enumerate(fetched_items):
            if isinstance(item, Task):
                actual_tasks.append(item)
            elif isinstance(item, list):
                print(f"Debug: get_todoist_tasks (filter attempt): Item {item_index+1} is a list. Processing inner items.")
                for inner_item_index, inner_item in enumerate(item):
                    if isinstance(inner_item, Task):
                        actual_tasks.append(inner_item)
                    else:
                        print(f"Debug: get_todoist_tasks (filter attempt): Inner item {inner_item_index+1} in list {item_index+1} is type: {type(inner_item)}. Content: {str(inner_item)[:100]}")
            else:
                print(f"Debug: get_todoist_tasks (filter attempt): Item {item_index+1} type: {type(item)}. Content: {str(item)[:100]}")
        
        print(f"Debug: get_todoist_tasks (filter attempt): Extracted {len(actual_tasks)} Task objects.")
        if actual_tasks:
            print(f"Debug: get_todoist_tasks: Successfully fetched {len(actual_tasks)} tasks using filter (or processed list structure).")
            return actual_tasks
        else:
            print("Debug: get_todoist_tasks (filter attempt): Filter 'due: {today}' (or list processing) yielded no tasks. Will try fallback if filter was the cause.")

    except TypeError as e:
        if "unexpected keyword argument 'filter'" in str(e):
            print(f"Warning: get_todoist_tasks: The 'filter' argument is not supported by your todoist-api-python version. Error: {e}")
        else:
            print(f"Warning: get_todoist_tasks: TypeError during filtered fetch: {e}")
    except TodoistAPIException as e:
        print(f"Warning: get_todoist_tasks: TodoistAPIException with filter='due: {today}': {e}")
    except Exception as e:
        print(f"Warning: get_todoist_tasks: Unexpected error during filtered fetch: {e}")

    # Fallback: Fetch all tasks if the filtered attempt failed or yielded nothing suitable
    print("Debug: get_todoist_tasks: Falling back to fetching all tasks without API filter.")
    actual_tasks = []
    try:
        all_tasks_response = api.get_tasks()
        fetched_all_items = list(all_tasks_response) if all_tasks_response else []

        print(f"Debug: get_todoist_tasks (fallback): Received {len(fetched_all_items)} raw items from API.")

        for item_index, item in enumerate(fetched_all_items):
            if isinstance(item, Task):
                actual_tasks.append(item)
            elif isinstance(item, list):
                print(f"Debug: get_todoist_tasks (fallback): Item {item_index+1} is a list. Processing inner items.")
                for inner_item_index, inner_item in enumerate(item):
                    if isinstance(inner_item, Task):
                        actual_tasks.append(inner_item)
                        print(f"Debug: get_todoist_tasks (fallback): Appended Task from inner list: {inner_item.content[:50]}...")
                    else:
                        print(f"Debug: get_todoist_tasks (fallback): Inner item {inner_item_index+1} in list {item_index+1} is type: {type(inner_item)}. Content: {str(inner_item)[:100]}")
            else:
                print(f"Debug: get_todoist_tasks (fallback): Item {item_index+1} type: {type(item)}. Content: {str(item)[:100]}")
        
        print(f"Debug: get_todoist_tasks (fallback): Extracted {len(actual_tasks)} Task objects after processing.")
        if not actual_tasks:
             print("Debug: get_todoist_tasks (fallback): No tasks found even in fallback after processing.")
        return actual_tasks

    except TodoistAPIException as e: 
        print(f"Error: get_todoist_tasks (fallback): TodoistAPIException when fetching all tasks: {e}")
    except Exception as e:
        print(f"Error: get_todoist_tasks (fallback): Failed to fetch all tasks: {e}")
    
    return []

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

def perform_single_sync_cycle(event=None, context=None): # Add event, context for GCF compatibility
    """Performs one complete synchronization cycle from Todoist to Habitica and back."""
    
    # Initialize or load state
    global todoist_to_habitica_map # Use global map for this cycle
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
    # Removed initial print statements about env vars for brevity in scheduled task logs
    # If needed for debugging, they can be re-added.

    # print("\n--- Running sync cycle ---") # Not needed for single run by scheduler
    # Get today's date in EST timezone
    est_now = datetime.now(TIMEZONE)
    today_date = est_now.date()
    today_date_str = today_date.isoformat()
    print(f"Filtering for tasks due on: {today_date_str} (EST)")

    # 1. FETCH DATA
    all_todoist_tasks_from_api = get_todoist_tasks(todoist_api)
    todoist_tasks_by_id_map = {task.id: task for task in all_todoist_tasks_from_api if isinstance(task, Task)}

    todoist_tasks_for_today: list[Task] = []
    if all_todoist_tasks_from_api:
        print(f"Debug: main_sync_loop: Received {len(all_todoist_tasks_from_api)} tasks from get_todoist_tasks. Now filtering for due date...")
        for task in all_todoist_tasks_from_api:
            if not isinstance(task, Task):
                print(f"Warning: main_sync_loop: Encountered non-Task object in list: {type(task)}. Content: {str(task)[:100]}")
                continue
            task_due_data = None
            if hasattr(task, 'due') and task.due and hasattr(task.due, 'date') and task.due.date:
                task_due_data = task.due.date
            else:
                continue
            task_due_date_obj = None
            if isinstance(task_due_data, str):
                try:
                    task_due_date_obj = datetime.strptime(task_due_data, "%Y-%m-%d").date()
                except ValueError as ve:
                    continue
            elif isinstance(task_due_data, date):
                task_due_date_obj = task_due_data
            else:
                continue
            # Strict equality check for today's date in EST
            if task_due_date_obj == today_date:
                print(f"Debug: Adding Todoist task '{task.content[:50]}...' (ID: {task.id}), due: {task_due_date_obj.isoformat()}")
                todoist_tasks_for_today.append(task)
            else:
                print(f"Debug: Skipping Todoist task '{task.content[:50]}...' (ID: {task.id}), due: {task_due_date_obj.isoformat()} (not today in EST)")

    print(f"Found {len(todoist_tasks_for_today)} active Todoist tasks due today after client-side filtering.")
    active_todoist_ids_today = {t.id for t in todoist_tasks_for_today}

    habitica_tasks = get_habitica_user_tasks()

    # 2. RECONCILE todoist_to_habitica_map WITH HABITICA TAGS
    # ... (existing logic for reconciliation, no changes needed here structurally) ...
    # This part remains unchanged:
    habitica_ids_with_valid_tags = set()
    # print(f"Debug: Reconciling todoist_to_habitica_map (current size: {len(todoist_to_habitica_map)}) with Habitica tags...") # Reduced verbosity
    for ht in habitica_tasks:
        if ht.get('type') == 'todo' and ht.get('notes') and '[TodoistID:' in ht['notes']:
            try:
                found_tid = ht['notes'].split('[TodoistID:')[1].split(']')[0]
                found_hid = ht['id']
                if found_tid:
                    habitica_ids_with_valid_tags.add(found_hid)
                    if found_tid not in todoist_to_habitica_map:
                        # print(f"Debug MAP-RECONCILE: Discovered new mapping from Habitica tag: T:{found_tid} -> H:{found_hid}. Adding to map.") # Reduced verbosity
                        todoist_to_habitica_map[found_tid] = found_hid
                    elif todoist_to_habitica_map[found_tid] != found_hid:
                        print(f"Warning MAP-RECONCILE: Mismatch for Todoist ID {found_tid}. Map had H:{todoist_to_habitica_map[found_tid]}, Habitica tag has H:{found_hid}. Updating map to Habitica tag's version.")
                        todoist_to_habitica_map[found_tid] = found_hid
            except IndexError:
                print(f"Warning MAP-RECONCILE: Could not parse Todoist ID from Habitica task notes: {ht.get('text')}")
    # print(f"Debug: todoist_to_habitica_map size after reconciliation: {len(todoist_to_habitica_map)}") # Reduced verbosity

    # --- Combined T->H Sync: Process mapped tasks for completion, rescheduling, or deletion --- 
    # ... (existing logic for combined T->H sync, no changes needed here structurally) ...
    # This part remains unchanged:
    # print("Debug T->H SYNC (Combined): Processing mapped tasks based on current Todoist status...") # Reduced verbosity
    ids_to_remove_from_map_after_combined_TH_sync = set()
    due_today_or_overdue_actual_ids = {t.id for t in todoist_tasks_for_today} 
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
                is_task_still_due_today = todoist_id in due_today_or_overdue_actual_ids
                if not is_task_still_due_today:
                    print(f"Debug T->H SYNC: Todoist task '{current_todoist_task_obj.content[:30]}' (TID:{todoist_id}) is RESCHEDULED (not completed, not due). Deleting H:{habitica_id}.")
                    if delete_habitica_task(habitica_id):
                        processed_completed_habitica_tasks.add(habitica_id) 
                    else:
                        print(f"Failed to delete stale Habitica task {habitica_id} for TID:{todoist_id}")
                    ids_to_remove_from_map_after_combined_TH_sync.add(todoist_id)
        else:
            if todoist_id not in processed_completed_todoist_tasks:
                print(f"Debug T->H SYNC: Todoist task (TID:{todoist_id}) from map not in API results (e.g. deleted/very old). Completing H:{habitica_id}.")
                if complete_habitica_task(habitica_id): 
                    processed_completed_todoist_tasks.add(todoist_id)
                    processed_completed_habitica_tasks.add(habitica_id)
                else:
                    print(f"Failed to complete Habitica task {habitica_id} for disappeared TID:{todoist_id}")
                ids_to_remove_from_map_after_combined_TH_sync.add(todoist_id)
    for tid_to_remove in ids_to_remove_from_map_after_combined_TH_sync:
        if tid_to_remove in todoist_to_habitica_map:
            # print(f"Debug T->H SYNC: Removing TID {tid_to_remove} from map.") # Reduced verbosity
            del todoist_to_habitica_map[tid_to_remove]

    # 4. SYNC COMPLETIONS: HABITICA -> TODOIST
    # ... (existing logic for H->T sync, no changes needed here structurally) ...
    # This part remains unchanged:
    # print("Debug H->T COMPLETION: Checking for Habitica tasks completed...") # Reduced verbosity
    ids_to_remove_from_map_after_H_T_sync = set()
    for h_task in habitica_tasks:
        h_id = h_task['id']
        h_text = h_task.get('text', 'Unknown Habitica Task')[:50]
        is_linked_via_tag = h_id in habitica_ids_with_valid_tags
        is_in_current_map_values = h_id in todoist_to_habitica_map.values()
        # if is_linked_via_tag or is_in_current_map_values:  # Reduced verbosity
            # print(f"Debug H->T CHECK: Habitica task '{h_text}...' (ID: {h_id}). API_Completed: {h_task.get('completed')}. Processed: {h_id in processed_completed_habitica_tasks}. LinkedByTag: {is_linked_via_tag}. InMapValues: {is_in_current_map_values}")
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
                        # print(f"Debug H->T COMPLETION: Found corresponding_tid {corresponding_tid} via notes for H:{h_id} as it was not in map's keys.") # Reduced verbosity
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
                # print(f"Debug H->T COMPLETION: Habitica task '{h_text}...' (ID: {h_id}) is API_Completed: True, but Todoist task {corresponding_tid} was already processed. Marking Habitica task as processed.") # Reduced verbosity
                processed_completed_habitica_tasks.add(h_id) 
            elif not corresponding_tid:
                 print(f"Debug H->T COMPLETION: Habitica task '{h_text}...' (ID: {h_id}) is API_Completed: True, but could not find its corresponding Todoist ID in map or notes. Marking as processed to avoid loops.")
                 processed_completed_habitica_tasks.add(h_id)
    for tid_to_remove in ids_to_remove_from_map_after_H_T_sync:
        if tid_to_remove in todoist_to_habitica_map: 
            # print(f"Debug H->T COMPLETION: Removing completed Todoist task {tid_to_remove} (via Habitica completion) from map.") # Reduced verbosity
            del todoist_to_habitica_map[tid_to_remove]

    # 5. SYNC NEW TASKS: TODOIST -> HABITICA
    # ... (existing logic for new task sync T->H, no changes needed here structurally) ...
    # This part remains unchanged:
    # print("Debug NEW TASK SYNC T->H: Checking for new Todoist tasks to sync to Habitica...") # Reduced verbosity
    for task in todoist_tasks_for_today: 
        if task.id not in todoist_to_habitica_map and not task.is_completed: 
            print(f"New uncompleted Todoist task due today/overdue: '{task.content[:50]}...'. Creating in Habitica...")
            habitica_notes = f"{task.description if task.description else ''}\n\n[TodoistID:{task.id}]"
            created_habitica_task = create_habitica_task_from_todoist(task.content, habitica_notes)
            if created_habitica_task and created_habitica_task.get('id'):
                new_hid = created_habitica_task['id']
                todoist_to_habitica_map[task.id] = new_hid
                print(f"Successfully created Habitica task for Todoist task '{task.content[:50]}...'. Mapped Todoist ID {task.id} to Habitica ID {new_hid}.")
            else:
                print(f"Failed to create Habitica task for Todoist task '{task.content[:50]}...'. Response: {created_habitica_task}")
        # elif task.id in todoist_to_habitica_map and not task.is_completed: # Reduced verbosity
             # print(f"Todoist task '{task.content[:50]}...' (ID: {task.id}) already mapped (H_ID: {todoist_to_habitica_map.get(task.id)}) and not completed. No action for new sync.")

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
