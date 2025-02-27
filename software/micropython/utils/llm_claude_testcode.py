class thing():
    def __init__(self):
        values_dict={"str1":[1,2,3,4,5],"str2":[1,2,3,4,5]}
        self.range_to_operate_with=values_dict("str1")[:2]
        self.update=False
        
    async def update_values(self,str_to_update):
        self.range_to_operate_with=values_dict(str_to_update)[:2]
        
    async def work_with_values(self):
        "lots of hard work going on in here, trust me"
        "fft stuff"
    
        if self.update=True:
            self.update_value("str2")