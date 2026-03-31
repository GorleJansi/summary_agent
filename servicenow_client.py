import requests
from config import SERVICENOW_INSTANCE, SERVICENOW_USERNAME, SERVICENOW_PASSWORD

BASE_URL = f"https://{SERVICENOW_INSTANCE}/api/now/table"
AUTH     = (SERVICENOW_USERNAME, SERVICENOW_PASSWORD)
HEADERS  = {"Accept": "application/json"}


def get_case_by_number(case_number: str):
    """Fetch a single case record by case number."""
    url    = f"{BASE_URL}/sn_customerservice_case"
    params = {
        "sysparm_query":         f"number={case_number}",
        "sysparm_fields":        (
            "sys_id,number,case,short_description,description,"
            "state,priority,severity,assignment_group,assigned_to,"
            "sys_created_on,sys_updated_on"
        ),
        "sysparm_limit":         "1",
        "sysparm_display_value": "all",
    }
    resp = requests.get(url, auth=AUTH, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    results = resp.json().get("result", [])
    return results[0] if results else None


def get_case_journal_entries(sys_id: str) -> list:
    """Fetch comments and work notes from sys_journal_field for a case."""
    url    = f"{BASE_URL}/sys_journal_field"
    params = {
        "sysparm_query":         (
            f"element_id={sys_id}^elementINcomments,work_notes"
            f"^ORDERBYsys_created_on"
        ),
        "sysparm_fields":        "sys_created_on,element,value,sys_created_by",
        "sysparm_display_value": "true",
    }
    resp   = requests.get(url, auth=AUTH, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    result = resp.json().get("result", [])

    # Fallback: some instances store by documentkey instead of element_id
    if not result:
        params["sysparm_query"] = (
            f"documentkey={sys_id}^elementINcomments,work_notes"
            f"^ORDERBYsys_created_on"
        )
        resp   = requests.get(url, auth=AUTH, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        result = resp.json().get("result", [])

    return result


def get_case_emails(sys_id: str) -> list:
    """
    Fetch emails linked to a case from sys_email.
    Filters by both instance (sys_id) and target_table to avoid
    pulling emails from unrelated records that share the same sys_id.
    """
    url    = f"{BASE_URL}/sys_email"
    params = {
        "sysparm_query": (
            f"instance={sys_id}"
            f"^target_table=sn_customerservice_case"
            f"^ORDERBYsys_created_on"
        ),
        "sysparm_fields": (
            "sys_id,sys_created_on,type,subject,body,body_text,"
            "sys_created_by,recipients,user,target_table,instance"
        ),
        "sysparm_display_value": "true",
    }
    resp = requests.get(url, auth=AUTH, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("result", [])