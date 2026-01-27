from datetime import datetime


class Nomenclature:
    def __init__(self, s_productNameIn, s_productArticleIn,
                 sl_productPropertiesIn = [], sl_productPriceIn = [], nl_productCountIn = [], s_productDescriptionIn = ""):
        self.s_productName = s_productNameIn
        self.s_productArticle = s_productArticleIn

        self.sl_productProperties = sl_productPropertiesIn
        self.sl_productPrice = sl_productPriceIn
        self.nl_productCount = nl_productCountIn

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

class orderItem:
    def __init__(self, s_productArticleIn, s_productPropertieIn, n_productCountIn):
        self.s_productArticle = s_productArticleIn
        self.s_productProperties = s_productPropertieIn
        self.n_productCount = n_productCountIn

class Order:
    def __init__(self, cus_orderCustomerIn, coritl_orderItemsListIn, n_orderCodeIn =0):
        self.cus_orderCustomer = cus_orderCustomerIn
        self.coritl_orderItemsList = coritl_orderItemsListIn
        self.s_TTN = ""
        self.s_status = ""
        self.s_date = datetime.now().strftime("%H:%M %d.%m.%Y")
        self.n_orderCode = n_orderCodeIn

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
        for item in self.coritl_orderItemsList:
            s_outString += f'\t\t⚫{item.s_productArticle}:{item.s_productProperties} - {item.n_productCount}\n'

        return s_outString