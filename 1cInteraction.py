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
        if not self.v8:
            print("No connection to 1C")
            return None

        try:
            new_order = self.v8.Documents.ЗаказКлиента.CreateDocument()
            new_order.Date = self.v8.CurrentDate()

            client_ref = self.v8.Catalogs.Контрагенты.FindByArticle(cor_orderIn.s_productArticle)
            if client_ref.IsEmpty():
                print(f"Client with code {cor_orderIn.s_productArticle} not found!")
                return False

            new_order.Контрагент = client_ref
            retail_price_type = self.v8.Catalogs.ВидыЦен.FindByName("Розничная")
            new_order.Организация = self.v8.Catalogs.Организации.GetPredefinedItem("ОсновнаяОрганизация")

            for item in cor_orderIn.noml_orderItemList:
                nom_ref = self.v8.Catalogs.Номенклатура.FindByArticle(item.article)
                if nom_ref.IsEmpty():
                    print(f"Product {item.article} not found, skipping...")
                    continue
                char_ref = self.v8.Catalogs.ХарактеристикиНоменклатуры.EmptyRef()
                if hasattr(item, 's_productProperties') and item.s_productProperties:
                    char_ref = self.v8.Catalogs.ХарактеристикиНоменклатуры.FindByName(item.s_productProperties, False,
                                                                                      nom_ref)
                    if char_ref.IsEmpty():
                        print(f"Characteristic {item.s_productProperties} for {item.s_productArticle} not found")
                filter_structure = self.v8.NewObject("Structure", "Номенклатура, ВидЦены", nom_ref, retail_price_type)
                if not char_ref.IsEmpty():
                    filter_structure.Insert("Характеристика", char_ref)

                price_structure = self.v8.InformationRegisters.ЦеныНоменклатуры.GetLast(
                new_order.Date, filter_structure)
                actual_price = price_structure.Цена if price_structure.Цена else 0

                row = new_order.Товары.Add()
                row.Номенклатура = nom_ref
                row.Характеристика = char_ref
                row.Количество = item.count
                row.Цена = actual_price
                row.Сумма = row.Количество * row.Цена

            new_order.Write(self.v8.DocumentWriteMode.Posting)

            print(f"Order created and posted: {new_order.Number}")
            return new_order.Number

        except Exception as e:
            print(f"Error while pushing order: {e}")
            return False

    def closeConnection(self):
        pass
