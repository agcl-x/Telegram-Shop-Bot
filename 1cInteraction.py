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
        try:
            connector = win32com.client.Dispatch("V83.COMConnector")
            self.v8 = connector.Connect(self.connection_string)
            print("Successfully connected to 1C on the local server.")
        except Exception as e:
            print(f"Failed to connect: {e}")
            self.v8 = None

    def getNomenclature(self, s_nameIn="", s_articleIn=""):
        if not self.v8: return None

        query = self.v8.NewObject("Query")
        query.Text = """
                    SELECT TOP 1
                        Ref, Description, Code
                    FROM
                        Catalog.Номенклатура
                    WHERE
                        Артикул = &Article OR Description = &Name
                """
        query.SetParameter("Article", s_articleIn)
        query.SetParameter("Name", s_nameIn)

        result = query.Execute()
        if not result.IsEmpty():
            selection = result.Select()
            selection.Next()
            return {
                "Name": selection.Description,
                "Code": selection.Code,
                "GUID": str(self.v8.String(selection.Ref.UUID()))
            }
        return None

    def pushOrder(self, cor_orderIn):
        pass

    def closeConnection(self):
        pass
