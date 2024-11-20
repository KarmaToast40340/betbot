import requests
import json


def get_page():
    url = "https://www.winamax.fr/paris-sportifs/sports/5"
    response = requests.get(
        url,
        headers={
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
        })
    html = response.text
    return html

def get_json():
    html = get_page()
    split1 = html.split("var PRELOADED_STATE = ")[1]
    split2 = split1.split(";</script>")[0]
    return json.loads(split2)

print (get_json())