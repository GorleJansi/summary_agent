from datetime import datetime  # Import datetime module to work with timestamps


# Function to clean text (remove newlines, extra spaces)
def clean_text(text: str) -> str:
    if not text:  # If text is empty or None
        return ""  # Return empty string
    
    # Replace carriage return and newline with space, then remove extra spaces
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


# Function to convert timestamp string into ISO format (standard format)
def to_iso(ts: str) -> str:
    # Convert string timestamp (ServiceNow format) to datetime object
    dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    
    # Convert datetime to ISO format and add 'Z' (UTC indicator)
    return dt.isoformat() + "Z"


# Function to map ServiceNow element to speaker type
def map_speaker(element: str) -> str:
    if element == "comments":  # If entry is from comments
        return "customer"  # It is from customer
    if element == "work_notes":  # If entry is from work notes
        return "support_engineer"  # It is from support engineer
    return "unknown"  # Default if not recognized


# Function to map element to event type
def map_type(element: str) -> str:
    if element == "comments":  # Customer message
        return "comment"
    if element == "work_notes":  # Internal engineer note
        return "work_note"
    return "event"  # Default type


# Function to build structured timeline from raw journal entries
def build_timeline(journal_entries: list) -> list:
    timeline = []  # Initialize empty list to store processed events

    # Loop through each journal entry (comments/work notes)
    for item in journal_entries:
        timeline.append({
            # Type of event (comment/work_note)
            "type": map_type(item.get("element", "")),

            # Who spoke (customer/support engineer)
            "speaker": map_speaker(item.get("element", "")),

            # Convert timestamp into ISO format
            "timestamp": to_iso(item["sys_created_on"]),

            # Clean and normalize text content
            "text": clean_text(item.get("value", "")),
        })

    return timeline  # Return structured timeline list




# It converts messy ticket data → clean structured timeline
# So LLM can understand properly.

# 👉 Input (raw ServiceNow data):

# {
#   "element": "comments",
#   "value": "Message failed\nPlease check",
#   "sys_created_on": "2026-03-12 09:15:00"
# }

# 👉 Output (clean structured format):

# {
#   "type": "comment",
#   "speaker": "customer",
#   "timestamp": "2026-03-12T09:15:00Z",
#   "text": "Message failed Please check"
# }