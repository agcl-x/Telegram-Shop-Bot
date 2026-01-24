from datetime import datetime


class Nomenclature:
    def __init__(self, s_productNameIn, s_productArticleIn,
                 sd_productСharacteristicsToPriceIn = {}, s_productDescriptionIn = ""):
        self.s_productName = s_productNameIn
        self.s_productArticle = s_productArticleIn
        self.sd_productСharacteristicsToPrice = sd_productСharacteristicsToPriceIn
        self.s_productDescription = s_productDescriptionIn

    def __str__(self):
        s_outString = (f"🔥{self.s_productName}🔥"
                       f"📝{self.s_productArticle}\n"
                       f"{self.s_productDescription}")
        return s_outString

class Customer:
    def __init__(self, s_customerTelegramIdIn, s_customerPIBIn,
                 s_customerPhoneIn, s_customerAddressIn):
        self.s_customerTelegramId = s_customerTelegramIdIn
        #Add check if user exists in database
        #Use existing db to save customers
        #Delete product and product properties tables from db

        self.s_customerPIB = s_customerPIBIn
        self.s_customerPhone = s_customerPhoneIn
        self.s_customerAddress = s_customerAddressIn

    def __str__(self):
        pass

class Order:
    natr_currOrderNumber = 1

    def __init__(self, cus_orderCustomerIn, noml_orderNomenclaturesListIn):
        self.cus_orderCustomer = cus_orderCustomerIn
        self.noml_orderNomenclaturesList = noml_orderNomenclaturesListIn
        self.s_TTN = ""
        self.s_status = ""
        self.date = datetime.now().strftime("%H:%M %d.%m.%Y")

    def __str__(self):
        s_outString = f'''\t<b>ЗАМОВЛЕННЯ №{self.natr_currOrderNumber}</b>
        📅Дата: {self.date}\n
        🔗Користувач: <a href="tg://user?id={self.cus_orderCustomer.s_customerTelegramId}">Замовник</a>
            🙎‍♂️ПІБ: {self.cus_orderCustomer.s_customerPIB}
            📞Номер телефону: {self.cus_orderCustomer.s_customerPhone}
            🏠Адреса: {self.cus_orderCustomer.s_customerAddres}\n
        🔢ТТН: {self.s_TTN}
        📩Статус: {self.s_status}\n
        📃Список покупок:\n'''
        for product in self.noml_orderNomenclaturesList:
            s_outString += f'\t\t⚫{product.s_productArticle}:{tovar["prop"]} - {tovar["count"]}\n'
