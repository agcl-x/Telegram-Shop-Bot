class Nomenclature:
    def __init__(self, s_productNameIn, s_productArticleIn,
                 s_productСharacteristicsToPriceIn = [], s_productDescriptionIn = ""):
        self.s_productName = s_productNameIn
        self.s_productArticle = s_productArticleIn
        self.s_productСharacteristicsToPrice = s_productСharacteristicsToPriceIn
        self.s_productDescription = s_productDescriptionIn

    def __str__(self):
        s_outString = (f"🔥{self.s_productName}🔥"
                       f"📝{self.s_productArticle}\n"
                       f"{self.s_productDescription}")
        return s_outString
