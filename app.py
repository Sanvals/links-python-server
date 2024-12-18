from flask import Flask, jsonify, request
from flask_cors import CORS
from io import BytesIO
import os
import requests
from datetime import datetime

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from oauth2client.service_account import ServiceAccountCredentials

# Environment variables
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
GOOGLE_API = os.getenv("GOOGLE_API")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

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

        # socketio.emit('new_url', {'url': current_url})
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


class createService:
    def __init__(self):
        self._SCOPES = ['https://www.googleapis.com/auth/drive']
        _base_path = os.path.dirname(__file__)
        # Make sure to adjust the file path correctly
        self._credential_path = os.path.join(_base_path, 'credential.json')

    def build(self):
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            self._credential_path, self._SCOPES
        )
        service = build('drive', 'v3', credentials=creds)
        return service


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"message": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "File without title"}), 400

    # Load file content into memory
    file_content = BytesIO(file.read())
    file_content.seek(0)  # Reset pointer to the start of the file

    # Create Drive service
    drive_service = createService().build()

    # Prepare media for upload
    media_body = MediaIoBaseUpload(
        file_content,
        mimetype=file.mimetype,
        resumable=True
        )

    created_at = datetime.now().strftime("%Y%m%d%H%M%S")
    file_metadata = {
        "name": f"{file.filename} ({created_at})",
        "parents": ["1cGpjpegdBEq8VX2SBP7aW8CJQzVZuY-h"]
    }

    returned_fields = "id, name, mimeType, webViewLink, exportLinks"

    try:
        # Upload the file to Google Drive
        upload_response = drive_service.files().create(
            body=file_metadata,
            media_body=media_body,
            fields=returned_fields
        ).execute()
        print(upload_response)

        return jsonify(upload_response)

    except Exception as e:
        print(f"Error uploading file: {e}")

        return jsonify({"message": "Error uploading file"}), 500


if __name__ == '__main__':
    app.run()
