import win32com.client
import json
import os

import dataStructures
import sqlInteraction
from log import log_sys


class Connection:
    def __init__(self):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        with open(config_path, "r") as file:
            self.config = json.load(file)

        self.connection_string = self.config["connectionString"]
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

    def save_image_from_1c(self, storage_value, file_name):
        """Зберігає картинку з ValueStorage 1С у тимчасовий файл"""
        import os

        # Створюємо папку temp, якщо немає
        temp_dir = "temp_images"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        full_path = os.path.abspath(os.path.join(temp_dir, file_name))

        try:
            # В 1С метод .Get() отримує двійкові дані, .Write() записує їх на диск
            # Якщо це COM-об'єкт BinaryData
            if storage_value:
                # Отримуємо BinaryData з ValueStorage
                binary_data = storage_value.Get()
                if binary_data:
                    binary_data.Write(full_path)
                    return full_path
        except Exception as e:
            print(f"Error saving image from 1C: {e}")
            return None
        return None

    def getProductData(self, s_articleIn):
        if not self.v8: return None

        # 1. Отримуємо дані про товар (Ціна, Залишок, Посилання)
        query = self.v8.NewObject("Query")
        query.Text = """
            ВЫБРАТЬ
                Ном.Ссылка КАК Ссылка,
                Ном.Наименование КАК Наименование,
                Ном.Артикул КАК Артикул,
                Ном.Описание КАК Описание,
                ЕСТЬNULL(Цены.Цена, 0) КАК Цена,
                ЕСТЬNULL(Остатки.ВНаличииОстаток, 0) КАК Остаток,
                ЕСТЬNULL(Характеристики.Наименование, "") КАК Размер
            ИЗ
                Справочник.Номенклатура КАК Ном

                ЛЕВОЕ СОЕДИНЕНИЕ Справочник.ХарактеристикиНоменклатуры КАК Характеристики
                ПО Характеристики.Владелец = Ном.Ссылка

                ЛЕВОЕ СОЕДИНЕНИЕ РегистрСведений.ЦеныНоменклатуры.СрезПоследних(&Период, ) КАК Цены
                ПО Цены.Номенклатура = Ном.Ссылка
                И (Цены.Характеристика = Характеристики.Ссылка ИЛИ Цены.Характеристика = ЗНАЧЕНИЕ(Справочник.ХарактеристикиНоменклатуры.ПустаяСсылка))

                ЛЕВОЕ СОЕДИНЕНИЕ РегистрНакопления.ТоварыНаСкладах.Остатки(&Период, ) КАК Остатки
                ПО Остатки.Номенклатура = Ном.Ссылка
                И (Остатки.Характеристика = Характеристики.Ссылка ИЛИ Остатки.Характеристика = ЗНАЧЕНИЕ(Справочник.ХарактеристикиНоменклатуры.ПустаяСсылка))
            ГДЕ
                Ном.Артикул = &Артикул
        """

        query.SetParameter("Артикул", s_articleIn)
        query.SetParameter("Период", self.v8.CurrentDate())

        result = query.Execute()
        if result.IsEmpty(): return None

        selection = result.Select()

        product_data = {
            "name": "",
            "art": s_articleIn,
            "ref": None,  # Збережемо посилання для пошуку картинок
            "about": "",
            "availabilityForProperties": {},
            "priceForProperties": {},
            "sizeList": [],
            "frontImage": None,
            "backImage": None
        }

        while selection.Next():
            if not product_data["name"]:
                product_data["name"] = selection.Наименование
                product_data["about"] = selection.Описание if hasattr(selection, "Описание") else ""
                product_data["ref"] = selection.Ссылка  # Зберігаємо COM-об'єкт посилання

            size = selection.Размер if selection.Размер else "Standard"
            # Фільтруємо, щоб додавати тільки якщо є залишок
            if float(selection.Остаток) > 0:
                product_data["availabilityForProperties"][size] = int(selection.Остаток)
                product_data["priceForProperties"][size] = int(selection.Цена)
                product_data["sizeList"].append(size)

        # 2. Отримуємо картинки (окремий запит для швидкодії)
        if product_data["ref"]:
            try:
                # Запит до приєднаних файлів.
                # УВАГА: Назва довідника може бути "НоменклатураПрисоединенныеФайлы" або просто "Файлы"
                # Залежить від конфігурації. Тут приклад для BAS/УТ.
                img_query = self.v8.NewObject("Query")
                img_query.Text = """
                    ВЫБРАТЬ ПЕРВЫЕ 2
                        Файлы.Ссылка КАК Ссылка,
                        Файлы.Расширение КАК Расширение,
                        Файлы.ХранимыйФайл КАК ХранимыйФайл
                    ИЗ
                        Справочник.НоменклатураПрисоединенныеФайлы КАК Файлы
                    ГДЕ
                        Файлы.Владелец = &Владелец
                        И НЕ Файлы.ПометкаУдаления
                    УПОРЯДОЧИТЬ ПО
                        Файлы.ДатаСоздания УБЫВ
                """
                img_query.SetParameter("Владелец", product_data["ref"])
                img_res = img_query.Execute()

                if not img_res.IsEmpty():
                    img_sel = img_res.Select()
                    counter = 0
                    while img_sel.Next():
                        # Генеруємо ім'я файлу
                        ext = str(img_sel.Расширение)
                        fname = f"{s_articleIn}_{counter}.{ext}"

                        # Зберігаємо файл
                        saved_path = self.save_image_from_1c(img_sel.ХранимыйФайл, fname)

                        if saved_path:
                            if counter == 0:
                                product_data["frontImage"] = saved_path
                            elif counter == 1:
                                product_data["backImage"] = saved_path
                        counter += 1
            except Exception as e:
                print(f"Error fetching images from 1C: {e}")

        return product_data
    def pushOrder(self, cor_orderIn):
        if not self.v8:
            print("No connection to 1C")
            return None

        try:
            new_order = self.v8.Documents.ЗаказКлиента.CreateDocument()
            new_order.Date = self.v8.CurrentDate()

            client_ref = self.v8.Catalogs.Контрагенты.FindByCode(self.config["1cContragentCode"])
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

    def getOrders(self, cus_orderCustomer=None, s_orderDate=None):
        if not self.v8:
            print("No connection to 1C")
            return None

        # --- Case 1: Fetching specific customer orders (Iterative logic) ---
        if cus_orderCustomer:
            return self._get_orders_by_customer(cus_orderCustomer, s_orderDate)

        # --- Case 2: Bulk search by date (Query logic) ---
        return self._get_orders_by_query(s_orderDate)

    def _get_orders_by_customer(self, cus_orderCustomer, s_orderDate):
        orders_list = []
        # Note: Ensure your SQL query is actually fetching order codes, not just *
        user_data = sqlInteraction.fetch_as_dicts(
            "SELECT order_code FROM users WHERE id = ?",
            (cus_orderCustomer.s_customerTelegramId,)
        )

        for row in user_data:
            order_ref = self.v8.Documents.ЗаказКлиента.FindByNumber(row['order_code'])
            if order_ref.IsEmpty():
                continue

            # Date Filter
            if s_orderDate and order_ref.Date.date() != s_orderDate:
                continue

            # Extract items
            items = [
                dataStructures.orderItem(
                    line.Номенклатура.Артикул,
                    line.Характеристика.Наименование if not line.Характеристика.IsEmpty() else "",
                    float(line.Количество)
                ) for line in order_ref.Товары
            ]

            # Build Order Object
            new_order = dataStructures.Order(
                cus_orderCustomerIn=cus_orderCustomer,
                coritl_orderItemsListIn=items,
                n_orderCodeIn=order_ref.Number
            )

            # Status & Metadata
            new_order.s_status = (str(order_ref.Статус) if hasattr(order_ref, "Статус")
                                  else ("Проведений" if order_ref.Posted else "Чернетка"))
            new_order.s_TTN = str(getattr(order_ref, "НомерТТН", ""))
            new_order.s_date = order_ref.Date.strftime("%H:%M %d.%m.%Y")

            orders_list.append(new_order)

        return orders_list

    def _get_orders_by_query(self, s_orderDate):
        query = self.v8.NewObject("Query")
        query_text = "SELECT Number, Date, СуммаДокумента AS TotalSum, Ref FROM Document.ЗаказКлиента WHERE 1=1"

        if s_orderDate:
            query_text += " AND Date BETWEEN &Beg AND &End"
            query.SetParameter("Beg", self.v8.BegOfDay(s_orderDate))
            query.SetParameter("End", self.v8.EndOfDay(s_orderDate))

        # Default to bot's client if no specific customer
        client_ref = self.v8.Catalogs.Контрагенты.FindByCode(self.config["1cContragentCode"])
        if not client_ref.IsEmpty():
            query_text += " AND Контрагент = &Customer"
            query.SetParameter("Customer", client_ref)

        query.Text = query_text
        res = query.Execute()

        if res.IsEmpty():
            return []

        selection = res.Select()
        results = []
        while selection.Next():
            results.append({
                "Number": selection.Number,
                "Date": str(selection.Date),
                "Sum": float(selection.TotalSum),
                "Ref": str(self.v8.String(selection.Ref.UUID()))
            })
        return results

    def closeConnection(self):
        self.v8 = None
