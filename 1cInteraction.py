import requests
from requests.auth import HTTPBasicAuth
import json

class Connection:
    def __init__(self):
        with open("config.json", "r") as file:
            config = json.load(file)
        # Ensure the URL ends correctly for the OData endpoint
        self.base_url = config["ODataBaseUrl"].rstrip('/') + "/standard.odata"
        self.auth = HTTPBasicAuth(config["1cUsername"], config["1cPassword"])
        self.session = requests.Session()
        self.session.auth = self.auth

        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })

    def closeConnection(self):
        pass

    def pushTo1c(self):
        pass

    def getFrom1c(self):
        pass