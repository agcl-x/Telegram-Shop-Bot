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

