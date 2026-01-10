import base64
from typing import Literal

accept_selection = {
    "json": "application/json",
    "html": "text/html",
}

def get_headers(name, passwd, *, accept: Literal["json", "html"]="json"):
    credentials = f"{name}:{passwd}"
    encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    headers = {
        "accept": accept_selection[accept],
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_credentials}"
    }
    return headers
