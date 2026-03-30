# import requests
# from config import SERVICENOW_INSTANCE, SERVICENOW_USERNAME, SERVICENOW_PASSWORD

# BASE_URL = f"https://{SERVICENOW_INSTANCE}/api/now/table"
# AUTH = (SERVICENOW_USERNAME, SERVICENOW_PASSWORD)
# HEADERS = {"Accept": "application/json"}


# def get_case_by_number(case_number: str):
#     url = f"{BASE_URL}/sn_customerservice_case"
#     params = {
#         "sysparm_query": f"number={case_number}",
#         "sysparm_fields": (
#             "sys_id,number,case,short_description,description,"
#             "state,sys_created_on,sys_updated_on"
#         ),
#         "sysparm_limit": "1",
#         "sysparm_display_value": "true",
#     }

#     resp = requests.get(
#         url,
#         auth=AUTH,
#         headers=HEADERS,
#         params=params,
#         timeout=30
#     )
#     resp.raise_for_status()

#     results = resp.json().get("result", [])
#     return results[0] if results else None


# def get_case_journal_entries(sys_id: str):
#     url = f"{BASE_URL}/sys_journal_field"
#     params = {
#         "sysparm_query": (
#             f"element_id={sys_id}^elementINcomments,work_notes^ORDERBYsys_created_on"
#         ),
#         "sysparm_fields": "sys_created_on,element,value,sys_created_by",
#         "sysparm_display_value": "true",
#     }

#     resp = requests.get(
#         url,
#         auth=AUTH,
#         headers=HEADERS,
#         params=params,
#         timeout=30
#     )
#     resp.raise_for_status()

#     result = resp.json().get("result", [])

#     if not result:
#         params["sysparm_query"] = (
#             f"documentkey={sys_id}^elementINcomments,work_notes^ORDERBYsys_created_on"
#         )
#         resp = requests.get(
#             url,
#             auth=AUTH,
#             headers=HEADERS,
#             params=params,
#             timeout=30
#         )
#         resp.raise_for_status()
#         result = resp.json().get("result", [])

#     return result


import requests

from config import SERVICENOW_INSTANCE, SERVICENOW_USERNAME, SERVICENOW_PASSWORD


BASE_URL = f"https://{SERVICENOW_INSTANCE}/api/now/table"
AUTH = (SERVICENOW_USERNAME, SERVICENOW_PASSWORD)
HEADERS = {"Accept": "application/json"}


def get_case_by_number(case_number: str):
    url = f"{BASE_URL}/sn_customerservice_case"

    params = {
        "sysparm_query": f"number={case_number}",
        "sysparm_fields": (
            "sys_id,number,case,short_description,description,"
            "state,priority,severity,assignment_group,assigned_to,"
            "sys_created_on,sys_updated_on"
        ),
        "sysparm_limit": "1",
        "sysparm_display_value": "all",
    }

    resp = requests.get(
        url,
        auth=AUTH,
        headers=HEADERS,
        params=params,
        timeout=30,
    )
    resp.raise_for_status()

    results = resp.json().get("result", [])
    return results[0] if results else None


def get_case_journal_entries(sys_id: str):
    url = f"{BASE_URL}/sys_journal_field"

    params = {
        "sysparm_query": (
            f"element_id={sys_id}^elementINcomments,work_notes^ORDERBYsys_created_on"
        ),
        "sysparm_fields": "sys_created_on,element,value,sys_created_by",
        "sysparm_display_value": "true",
    }

    resp = requests.get(
        url,
        auth=AUTH,
        headers=HEADERS,
        params=params,
        timeout=30,
    )
    resp.raise_for_status()

    result = resp.json().get("result", [])

    if not result:
        params["sysparm_query"] = (
            f"documentkey={sys_id}^elementINcomments,work_notes^ORDERBYsys_created_on"
        )
        resp = requests.get(
            url,
            auth=AUTH,
            headers=HEADERS,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json().get("result", [])

    return result