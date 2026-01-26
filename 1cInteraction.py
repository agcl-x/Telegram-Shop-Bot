import win32com.client
import json
import os


class Connection:
    def __init__(self):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        with open(config_path, "r") as file:
            config = json.load(file)

        self.connection_string = config["connectionString"]
        self.v8 = None
        self.initiateConnection()

    def initiateConnection(self):
        pass

    def getNomenclature(self, s_nameIn="", s_articleIn=""):
        pass

    def pushOrder(self, cor_orderIn):
        pass

    def closeConnection(self):
        pass
