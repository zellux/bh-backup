import requests
import logging
import os
import http.client
import argparse
from dataclasses import dataclass
from dotenv import load_dotenv, find_dotenv
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)

# http.client.HTTPConnection.debuglevel = 1
# requests_log = logging.getLogger("requests.packages.urllib3")
# requests_log.setLevel(logging.DEBUG)
# requests_log.propagate = True

@dataclass
class BHAttachment:
    id: str
    attachment_id: str
    for_date: str

class BHClient:
    BRIGHT_HORIZONS_BASE = 'https://bhlogin.brighthorizons.com'
    API_BASE = 'https://mbdgw.brighthorizons.com'
    DOWNLOAD_DIR = 'downloads'

    # API endpoints
    AUTH_ENDPOINT = f'{API_BASE}/auth/parent'
    PROFILE_ENDPOINT = f'{API_BASE}/parent/user/profile'
    GUARDIAN_ENDPOINT = f'{API_BASE}/parent/dependents/guardian'
    MEDIA_ENDPOINT = f'{API_BASE}/parent/dependent/memories/media'
    DOWNLOAD_LINK_ENDPOINT = f'{API_BASE}/parent/medias'

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.access_token = None
        self._children = None
        self.profile = None
        self.guardian_id = None

        self.session.headers.update({
            'Accept': '*/*',
            'Accept-Version': '2',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.5',
            'X-Backend-Version': 'standard',
            'User-Agent': 'my-bright-day-store/11.344.10 CFNetwork/3826.400.120 Darwin/24.3.0',
            'X-App-Version': 'my-bright-day/11.344.10',
            'Mbd-Server-Dependency': '2',
        })

    def log_in(self):
        if self.access_token is None:
            auth_response = self.session.post(self.AUTH_ENDPOINT, json={
                "username": self.username,
                "password": self.password
            })
            auth_response.raise_for_status()

            auth_response_json = auth_response.json()
            self.access_token = auth_response_json.get("accessToken")

        self.session.headers.update({
            'Authorization': f'Bearer {self.access_token}'
        })
        logging.debug('access_token: %s', self.access_token)
        logging.info('Login successful!')


    def retrieve_children(self):
        logging.debug('Session headers before request: %s', self.session.headers)
        profile_response = self.session.get(self.PROFILE_ENDPOINT)
        profile_response.raise_for_status()
        self.profile = profile_response.json()
        self.guardian_id = self.profile.get("id")
        logging.debug('guardian_id: %s', self.guardian_id)

        today = datetime.now().strftime('%Y-%m-%d')
        children_response = self.session.get(f'{self.GUARDIAN_ENDPOINT}/{self.guardian_id}/{today}?device_timezone=America/Los_Angeles')
        children_response.raise_for_status()
        logging.debug('Children response: %s', children_response.text)
        self.dependents = [e['id'] for e in children_response.json()['dependents']]
        logging.debug('children: %s', self.dependents)
        logging.info('Retrieved %d children', len(self.dependents))


    def retrieve_attachments(self, date) -> list[BHAttachment]:
        start_date = (date - timedelta(days=2)).strftime('%Y-%m-%d')
        end_date = date.strftime('%Y-%m-%d')
        resp = self.session.post(f'{self.MEDIA_ENDPOINT}?start_date={start_date}&end_date={end_date}', json=self.dependents)
        resp.raise_for_status()
        logging.debug('Retrieved %d attachment ids', len(resp.json()))
        attachments = []
        for e in resp.json():
            attachments.append(BHAttachment(id=e['id'], attachment_id=e['attachment_id'], for_date=e['for_date']))
        return attachments

    def download_attachments(self, attachments: list[BHAttachment]):
        logging.info('Downloading %d attachments', len(attachments))
        resp = self.session.post(self.DOWNLOAD_LINK_ENDPOINT, json={
            'mediaids': [a.attachment_id for a in attachments],
            'thumbnail': False,
        })
        attachment_id_to_date = {a.attachment_id: a.for_date for a in attachments}
        resp.raise_for_status()
        resp_json = resp.json()['medias']
        logging.debug('Retrieved %d media links', len(resp_json))
        for media_id, media_data in resp_json.items():
            if not os.path.exists(self.DOWNLOAD_DIR):
                os.makedirs(self.DOWNLOAD_DIR)

            filename = f'{self.DOWNLOAD_DIR}/{attachment_id_to_date[media_id]}_{media_data['filename']}'
            if os.path.exists(filename):
                logging.info('Skipping %s because it already exists', filename)
                continue

            resp = self.session.get(media_data['signed_url'])
            resp.raise_for_status()
            with open(filename, 'wb') as f:
                f.write(resp.content)
            logging.info('Downloaded %s', filename)

        return resp_json


if __name__ == "__main__":
    load_dotenv()
    load_dotenv(find_dotenv(usecwd=True))

    parser = argparse.ArgumentParser(description='Download Bright Horizons attachments')
    parser.add_argument('--days', type=int, default=7,
                      help='Number of days to look back for attachments (default: 7)')
    args = parser.parse_args()

    username = os.getenv("BH_USERNAME")
    password = os.getenv("BH_PASSWORD")
    if not username or not password:
        raise ValueError("BH_USERNAME and BH_PASSWORD must be set")

    client = BHClient(os.getenv("BH_USERNAME"), os.getenv("BH_PASSWORD"))
    client.log_in()
    client.retrieve_children()

    # go through the specified number of days, possible duplicates but will handle dedupe in download stage
    for i in range(args.days):
        today = datetime.now() - timedelta(days=i)
        attachments = client.retrieve_attachments(today)
        client.download_attachments(attachments)
