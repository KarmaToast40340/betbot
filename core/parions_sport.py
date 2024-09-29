import requests


def get_page():
    url = "https://www.enligne.parionssport.fdj.fr/paris-tennis"
    response = requests.get(
        url,
        headers={
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
        })
    html = response.text
    return html


def get_html():
    html = get_page()
    split1 = html.split('<body class="psel">')[1]
    split2 = split1.split('<p>Sur notre site')[0]
    return split2