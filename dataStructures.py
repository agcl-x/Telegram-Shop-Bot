from datetime import datetime

class Nomenclature:
    def __init__(self, s_productNameIn, s_productArticleIn,
                 sl_productPropertiesIn=[], sl_productPriceIn=[], nl_productCountIn=[], s_productDescriptionIn=""):
        self.s_productName = s_productNameIn
        self.s_productArticle = s_productArticleIn
        self.sl_productProperties = sl_productPropertiesIn
        self.sl_productPrice = sl_productPriceIn
        self.nl_productCount = nl_productCountIn
        self.s_productDescription = s_productDescriptionIn

    def __str__(self):
        return f"🔥{self.s_productName}🔥\n📝{self.s_productArticle}\n{self.s_productDescription}"

class Customer:
    def __init__(self, s_customerTelegramIdIn, s_customerPIBIn,
                 s_customerPhoneIn, s_customerAddressIn):
        self.s_customerTelegramId = s_customerTelegramIdIn
        self.s_customerPIB = s_customerPIBIn
        self.s_customerPhone = s_customerPhoneIn
        self.s_customerAddress = s_customerAddressIn

class orderItem:
    def __init__(self, s_productArticleIn, s_productPropertieIn, n_productCountIn):
        self.s_productArticle = s_productArticleIn
        self.s_productProperties = s_productPropertieIn
        self.n_productCount = n_productCountIn

class Order:
    def __init__(self, cus_orderCustomerIn, coritl_orderItemsListIn, n_orderCodeIn=0, s_dateIn=None):
        self.cus_orderCustomer = cus_orderCustomerIn
        self.coritl_orderItemsList = coritl_orderItemsListIn
        self.s_TTN = ""
        self.s_status = ""
        self.s_date = s_dateIn if s_dateIn else datetime.now().strftime("%H:%M %d.%m.%Y")
        self.n_orderCode = n_orderCodeIn

    def __str__(self):
        s_outString = f'''\t<b>ЗАМОВЛЕННЯ №{self.n_orderCode}</b>
        📅Дата: {self.s_date}\n
        🔗Користувач: <a href="tg://user?id={self.cus_orderCustomer.s_customerTelegramId}">Замовник</a>
            🙎‍♂️ПІБ: {self.cus_orderCustomer.s_customerPIB}
            📞Номер телефону: {self.cus_orderCustomer.s_customerPhone}
            🏠Адреса: {self.cus_orderCustomer.s_customerAddress}\n
        🔢ТТН: {self.s_TTN}
        📩Статус: {self.s_status}\n
        📃Список покупок:\n'''
        for item in self.coritl_orderItemsList:
            s_outString += f'\t\t⚫{item.s_productArticle}:{item.s_productProperties} - {item.n_productCount}\n'

        return s_outString