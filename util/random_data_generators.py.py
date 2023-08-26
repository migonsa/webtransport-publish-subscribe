import json, asyncio, os, sys, aiohttp
sys.path.append("../util/") # absolute path to util's folder
from util import printflush, RANDOM_SIZE, RANDOM_ORDER



class JSON: # base class

    def __init__(self, url):
        self.data_queue: asyncio.Queue[str] = asyncio.Queue()
        self.id = int.from_bytes(os.urandom(RANDOM_SIZE), RANDOM_ORDER)
        self.task = asyncio.ensure_future(self.__task__())
        self.url = url

    async def __call__(self):
        res = await self.data_queue.get()
        self.data_queue.task_done()
        return res
    
    def items(self, result):
        return result
        
    async def __read_data__(self, session):
        async with session.get(self.url) as response:
            result = await response.json()
            for item in self.items(result):
                item.update({"generator_id":self.id})
                self.id += 1
                await self.data_queue.put(json.dumps(item))

    async def __task__(self):
        async with aiohttp.ClientSession() as session:
            await self.__read_data__(session)
            while(True):
                empty = self.data_queue.join()
                await self.__read_data__(session)
                await empty

    async def terminate(self):
        try:
            await asyncio.wait_for(self.task, 0.001)
        except:
            pass


class JSON1(JSON): 	#from https://jservice.io/
										#sample JSON message: {"id":53311,"answer":"Hot air","question":"Propane-fueled burners provide this to lift balloons; politicians make their own","value":100,"airdate":"1998-03-25T19:00:00.000Z","created_at":"2022-12-30T19:00:15.915Z","updated_at":"2022-12-30T19:00:15.915Z","category_id":4282,"game_id":217,"invalid_count":null,"category":{"id":4282,"title":"balloons","created_at":"2022-12-30T19:00:15.856Z","updated_at":"2022-12-30T19:00:15.856Z","clues_count":5}}

    def __init__(self):
        super().__init__('https://jservice.io/api/random?count=100')


class JSON2(JSON): #from https://random-data-api.com/documentation
										#sample JSON message: {"id":3051,"uid":"0e82984d-11bb-4d0a-b020-ae667ee349a6","password":"KQLzVH2okN","first_name":"Florentino","last_name":"Dickens","username":"florentino.dickens","email":"florentino.dickens@email.com","avatar":"https://robohash.org/aliquamveritatisest.png?size=300x300\u0026set=set1","gender":"Genderfluid","phone_number":"+673 1-965-506-5530 x318","social_insurance_number":"240558296","date_of_birth":"1964-08-15","employment":{"title":"Senior Technology Officer","key_skill":"Work under pressure"},"address":{"city":"Stokesmouth","street_name":"Witting Skyway","street_address":"7404 Feil Courts","zip_code":"33973","state":"Nebraska","country":"United States","coordinates":{"lat":12.635035230316703,"lng":-62.47190790386587}},"credit_card":{"cc_number":"4336997120534"},"subscription":{"plan":"Bronze","status":"Pending","payment_method":"WeChat Pay","term":"Full subscription"}}

    def __init__(self):
        super().__init__('https://random-data-api.com/api/v2/users?size=100')


class JSON3(JSON): #from https://random-data-api.com/documentation
										#sample JSON message: {"id":9688,"uid":"5b40c2cc-7a39-4364-94cb-32ebd08a64e7","city":"Deidreside","street_name":"Sawayn Common","street_address":"9648 Rath Shore","secondary_address":"Suite 424","building_number":"309","mail_box":"PO Box 1191","community":"Willow Oaks","zip_code":"72381","zip":"33582","postcode":"53078-1944","time_zone":"Europe/Skopje","street_suffix":"Squares","city_suffix":"berg","city_prefix":"Port","state":"Florida","state_abbr":"NM","country":"Belarus","country_code":"VU","latitude":41.88238266230755,"longitude":-65.1191366254557,"full_address":"6475 Altenwerth Cape, Masonbury, WA 68318-8164"}
										
    def __init__(self):
        super().__init__('https://random-data-api.com/api/v2/addresses?size=100')
    

class JSON4(JSON): #from https://random-data-api.com/documentation
										#sample JSON message: {"id":4814,"uid":"b2bff963-cccf-4569-9079-1f137da59d5c","account_number":"7656146981","iban":"GB25FERQ74046254647488","bank_name":"ABU DHABI ISLAMIC BANK","routing_number":"253123145","swift_bic":"BOFAGB3SSWI"}
										
    def __init__(self):
        super().__init__('https://random-data-api.com/api/v2/banks?size=100')


class JSON5(JSON): #from https://random-data-api.com/documentation
										#sample JSON message: {"id":5099,"uid":"358410f2-e691-44e2-84d4-250b6fbaee47","brand":"Admiral","equipment":"Ceiling fan"}

    def __init__(self):
        super().__init__('https://random-data-api.com/api/v2/appliances?size=100')


class JSON6(JSON): #from https://random-data-api.com/documentation
										#sample JSON message: {"id":9554,"uid":"098518ab-bb5c-4ca5-9a3c-69c600934d9b","brand":"Lowenbrau","name":"Maharaj","style":"German Wheat And Rye Beer","hop":"Citra","yeast":"5335 - Lactobacillus","malts":"Special roast","ibu":"95 IBU","alcohol":"4.4%","blg":"19.6 Blg"}

    def __init__(self):
        super().__init__('https://random-data-api.com/api/v2/beers?size=100')


class JSON7(JSON): #from https://random-data-api.com/documentation
										#sample JSON message: {"id":9094,"uid":"fa9b2a26-ac54-49f2-90ba-7a5117a378e6","type":"AB","rh_factor":"-","group":"A+"}

    def __init__(self):
        super().__init__('https://random-data-api.com/api/v2/blood_types?size=100')


class JSON8(JSON): #from https://random-data-api.com/documentation
										#sample JSON message: {"id":9724,"uid":"446af411-900f-49a1-97c8-cf68bebd8e9b","credit_card_number":"1234-2121-1221-1211","credit_card_expiry_date":"2026-08-23","credit_card_type":"visa"}

    def __init__(self):
        super().__init__('https://random-data-api.com/api/v2/credit_cards?size=100')


class JSON9(JSON): #from https://fakerapi.it/en
										#sample JSON message: {"id":1,"street":"5545 Stevie Garden Apt. 004","streetName":"Aliyah Turnpike","buildingNumber":"844","city":"New Angie","zipcode":"16860","country":"Cocos (Keeling) Islands","county_code":"KG","latitude":84.072146,"longitude":80.598545}

    def __init__(self):
        super().__init__('https://fakerapi.it/api/v1/addresses?_quantity=100')

    def items(self, result):
        return result['data']


class JSON10(JSON): #from https://fakerapi.it/en
										#sample JSON message: {"id":1,"title":"So she went on.","author":"Serena Kreiger","genre":"Quia","description":"King replied. Here the Queen till she was considering in her face, with such sudden violence that Alice had got burnt, and eaten up by two guinea-pigs, who were lying round the court was a sound of.","isbn":"9786048501631","image":"http:\/\/placeimg.com\/480\/640\/any","published":"1989-10-29","publisher":"Ad Repellat"}

    def __init__(self):
        super().__init__('https://fakerapi.it/api/v1/books?_quantity=100')

    def items(self, result):
        return result['data']


class JSON11(JSON): #from https://fakerapi.it/en
										#sample JSON message: {"id":1,"name":"Huels-Hermann","email":"kovacek.leone@hotmail.com","vat":"23426428","phone":"+3657003527514","country":"Japan","addresses":[{"id":0,"street":"8307 Jenkins Mall Suite 166","streetName":"Lebsack Junction","buildingNumber":"571","city":"Reillyville","zipcode":"77242","country":"Ghana","county_code":"CF","latitude":-51.126463,"longitude":85.712615},{"id":0,"street":"7791 Willms Courts","streetName":"Victor Tunnel","buildingNumber":"41704","city":"South Marilyne","zipcode":"04648-7100","country":"Nigeria","county_code":"BD","latitude":-82.837923,"longitude":161.815272},{"id":0,"street":"4024 Haley Vista","streetName":"Casey Shoals","buildingNumber":"994","city":"West Aidamouth","zipcode":"14454","country":"Dominica","county_code":"IT","latitude":-26.714135,"longitude":-51.29074},{"id":0,"street":"638 Dietrich Wells","streetName":"Halle Court","buildingNumber":"303","city":"Jastland","zipcode":"82086-4978","country":"Korea","county_code":"CH","latitude":-72.244729,"longitude":-36.443629}],"website":"http:\/\/larson.net","image":"http:\/\/placeimg.com\/640\/480\/people","contact":{"id":0,"firstname":"Adelia","lastname":"Kohler","email":"yasmin.emmerich@gmail.com","phone":"+8657068304477","birthday":"2023-05-24","gender":"female","address":{"id":0,"street":"34276 Lakin Row Apt. 544","streetName":"Gibson Gateway","buildingNumber":"203","city":"South Camrenchester","zipcode":"91141-2019","country":"United States Minor Outlying Islands","county_code":"SV","latitude":-46.858105,"longitude":-134.003016},"website":"http:\/\/shanahan.com","image":"http:\/\/placeimg.com\/640\/480\/people"}}

    def __init__(self):
        super().__init__('https://fakerapi.it/api/v1/companies?_quantity=100')

    def items(self, result):
        return result['data']


class JSON12(JSON): #from https://fakerapi.it/en
										#sample JSON message: {"type":"MasterCard","number":"6011598033571453","expiration":"10\/23","owner":"Victoria Jenkins"}

    def __init__(self):
        super().__init__('https://fakerapi.it/api/v1/credit_cards?_quantity=100')

    def items(self, result):
        return result['data']


class JSON13(JSON): #from https://fakerapi.it/en
										#sample JSON message: {"title":"Qui inventore aut vitae sed.","description":"Tempore expedita ipsa sit. Voluptatem ut quis sint cum nisi. Porro pariatur voluptatem qui doloremque fugiat eveniet. Cumque voluptatibus nulla a adipisci nostrum.","url":"http:\/\/placeimg.com\/640\/480\/any"}

    def __init__(self):
        super().__init__('https://fakerapi.it/api/v1/images?_quantity=100')

    def items(self, result):
        return result['data']


class JSON14(JSON): #from https://fakerapi.it/en
										#sample JSON message: {"id":1,"firstname":"Therese","lastname":"Johnson","email":"earnest.satterfield@lehner.com","phone":"+6163067449078","birthday":"1950-08-01","gender":"female","address":{"id":0,"street":"488 Casimer Orchard Apt. 131","streetName":"Rolfson Wells","buildingNumber":"7232","city":"East Bethel","zipcode":"11333-6103","country":"Hungary","county_code":"BS","latitude":32.925239,"longitude":64.721886},"website":"http:\/\/medhurst.net","image":"http:\/\/placeimg.com\/640\/480\/people"}

    def __init__(self):
        super().__init__('https://fakerapi.it/api/v1/persons?_quantity=100')

    def items(self, result):
        return result['data']


class JSON15(JSON): #from https://fakerapi.it/en
										#sample JSON message: {"id":1,"name":"Alias maxime unde rerum.","description":"Officiis consequatur veniam expedita molestiae in nisi quo quidem. Quia tempore voluptatem sit ipsum et. Assumenda impedit sit qui minus maiores omnis omnis.","ean":"2057771708923","upc":"014816996119","image":"http:\/\/placeimg.com\/640\/480\/tech","images":[{"title":"Est sequi in possimus nihil.","description":"Consectetur sint voluptas quam recusandae. Dignissimos sed est odio perspiciatis. Voluptatibus qui illum et repellat. Ut modi mollitia excepturi aut molestiae dolores. Est nihil aut beatae quos sed.","url":"http:\/\/placeimg.com\/640\/480\/any"},{"title":"Sit et ut sapiente.","description":"Dolor et ratione et veniam in quia. Minima magnam dolorem sit. Molestiae a saepe libero doloremque est laudantium rerum. Consequuntur officiis amet temporibus qui rem vitae.","url":"http:\/\/placeimg.com\/640\/480\/any"},{"title":"Dolores quia dolor est eos.","description":"Et aut saepe dolores voluptatem quidem. Voluptatem ut quae dolorem sapiente iure cumque architecto. Ea quaerat deleniti porro officia. Veniam soluta cumque tempora ut aut veritatis voluptatem.","url":"http:\/\/placeimg.com\/640\/480\/any"}],"net_price":184284.94,"taxes":22,"price":"224827.63","categories":[7,2,9,3],"tags":["fuga","quia","maxime","dolorum","est","dicta","voluptas","amet","provident","nulla"]}

    def __init__(self):
        super().__init__('https://fakerapi.it/api/v1/products?_quantity=100')

    def items(self, result):
        return result['data']


class JSON16(JSON): #from https://fakerapi.it/en
										#sample JSON message: {"title":"I beg your.","author":"Terrance Stoltenberg","genre":"Rerum","content":"She said the Duck: 'it's generally a frog or a watch to take MORE than nothing.' 'Nobody asked YOUR opinion,' said Alice. 'Come, let's try Geography. London is the capital of Rome, and Rome--no, THAT'S all wrong, I'm certain! I must go back by railway,' she said to the jury, of course--\"I GAVE HER ONE, THEY GAVE HIM TWO--\" why, that must be growing small again.' She got up this morning, but I hadn't gone down that rabbit-hole--and yet--and yet--it's rather curious, you know, upon the other."}

    def __init__(self):
        super().__init__('https://fakerapi.it/api/v1/texts?_characters=500&_quantity=100')

    def items(self, result):
        return result['data']


class JSON17(JSON): #from https://fakerapi.it/en
										#sample JSON message: {"id":1,"uuid":"7fff6e0d-517e-3c11-bd24-55db292749f8","firstname":"Ardella","lastname":"Hagenes","username":"hintz.clint","password":"VY]M%\/^Yra*^\"&;\\nKA","email":"lrosenbaum@kemmer.biz","ip":"24.154.224.253","macAddress":"49:62:42:D4:93:FD","website":"http:\/\/runolfsson.com","image":"http:\/\/placeimg.com\/640\/480\/people"}

    def __init__(self):
        super().__init__('https://fakerapi.it/api/v1/users?_quantity=100')

    def items(self, result):
        return result['data']


class JSON18(JSON): #from https://fakerapi.it/en
										#sample JSON message: {"field1":"Alice again, for she had found the fan and gloves--that is, if I can do no more, whatever happens. What WILL become of me? They're dreadfully fond of pretending to be a person of authority over."}

    def __init__(self):
        super().__init__('https://fakerapi.it/api/v1/custom?field1=long_text&_quantity=100')

    def items(self, result):
        return result['data']


class JSON19(JSON): #from https://fakerapi.it/en
										#sample JSON message: {"field1":"4024007108179663","field2":"1987-07-11","field3":41.455095,"field4":-156.950062,"field5":"045397686442","field6":"102104108","field7":"04408-4623","field8":3772157}

    def __init__(self):
        super().__init__('https://fakerapi.it/api/v1/custom?field1=card_number&field2=date&field3=latitude&field4=longitude&field5=upc&field6=vat&field7=postcode&field8=number&_quantity=100')

    def items(self, result):
        return result['data']


class JSON20(JSON): #from https://randomuser.me/documentation
										#sample JSON message: {"gender":"female","name":{"title":"Miss","first":"Janet","last":"Peters"},"location":{"street":{"number":9858,"name":"The Crescent"},"city":"Chichester","state":"Clwyd","country":"United Kingdom","postcode":"Y31 6FG","coordinates":{"latitude":"-11.6654","longitude":"60.7894"},"timezone":{"offset":"+5:30","description":"Bombay, Calcutta, Madras, New Delhi"}},"email":"janet.peters@example.com","login":{"uuid":"7b1bfd32-8869-4a87-a3cc-4f6f549092ad","username":"silverelephant976","password":"shrimp","salt":"GxJOHCjn","md5":"e1e7935c398bafbf44808ac274283aef","sha1":"b5f49873cca87cbe145eeca7d96c706e1e63dede","sha256":"d9b6e8e5585cffd8b88282b6286820fa37c84bdfd6542b4eb912b6b5a4140703"},"dob":{"date":"1967-01-19T06:46:54.737Z","age":56},"registered":{"date":"2021-03-06T11:04:38.373Z","age":2},"phone":"0114110 359 8167","cell":"07540 709021","id":{"name":"NINO","value":"MZ 82 14 56 Z"},"picture":{"large":"https://randomuser.me/api/portraits/women/31.jpg","medium":"https://randomuser.me/api/portraits/med/women/31.jpg","thumbnail":"https://randomuser.me/api/portraits/thumb/women/31.jpg"},"nat":"GB"}

    def __init__(self):
        super().__init__('https://randomuser.me/api/?results=100')

    def items(self, result):
        return result['results']

    

