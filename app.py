from flask import Flask, jsonify
from flask_cors import CORS
import os
import requests

# Environment variables
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

# Run flask app
app = Flask(__name__)
CORS(app)

# State variables
current_url = ""
current_data = {}
valid_urls = []
headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def fetch_pages():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    results = []
    has_more = True
    start_cursor = None

    # Loop until all pages are fetched
    while has_more:
        payload = {
            "filter": {
                "property": "Show",
                "checkbox": {"equals": True}
            },
            "page_size": 100
        }

        # Add the start_cursor to the payload if it's not None
        if start_cursor:
            payload["start_cursor"] = start_cursor

        # Make the request to Notion API
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        # Extend the results list with the current batch of results
        results.extend(data.get("results", []))

        # Update the pagination variables
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor", None)

    # print(f"Total items fetched: {len(results)}")
    return results


@app.route("/refresh", methods=['GET'])
def refresh_data():
    global current_data
    results = fetch_pages()

    clean = {}
    for result in results:
        prop = result["properties"]
        tag = prop.get("Tags", {}).get("select", {})
        tag = tag.get("name", "Uncategorized")
        link = {
            "tag": tag,
            "num": prop.get("Number", {}).get("number", 0),
            "name": prop.get("Name", {}).get("title", [{
                "text": {"content": "Untitled"
                         }}
                ])[0].get("text", {}).get("content", ""),
            "url": prop.get("URL", {}).get("url", ""),
            "icon": prop.get("Icon", {}).get("url", "")
        }

        # Check if tag exists in clean
        if tag not in clean:
            clean[tag] = []
        clean[tag].append(link)

        # Add url to valid_urls
        if link["url"] not in valid_urls:
            valid_urls.append(link["url"])

    # Sort tag groups by 'num' property
    for tag in clean:
        clean[tag] = sorted(clean[tag], key=lambda x: x["num"])

    # Sort tags alphabeticlaly and create sorted data
    sorted_clean_data = {tag: clean[tag] for tag in sorted(clean.keys())}
    current_data = sorted_clean_data
    return jsonify(sorted_clean_data)


@app.route('/', methods=['GET'])
def get_links():
    return current_data


@app.route('/set_url/<path:url>', methods=['GET'])
def set_url(url):
    global current_url

    url = 'https://' + url

    if url not in valid_urls:
        print("Entered an NOT VALID url")
        return jsonify({"message": "URL not valid"}), 400
    else:
        current_url = url
        print(f"URL set to: {current_url}")  # Debugging output
        return jsonify({"message": "URL set", "url": current_url})


@app.route('/get_url', methods=['GET'])
def get_url():
    return jsonify({"url": current_url})


@app.route('/empty', methods=['GET'])
def empty_url():
    global current_url
    current_url = ""
    print("Link emptied")
    return jsonify({"message": "Link emptied"})


if __name__ == '__main__':
    app.run()
