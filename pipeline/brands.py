"""Known chain brands in Idaho: regex on normalized name -> brand label.

Adapted from co-eats/pipeline/brands.py; Colorado-only brands dropped, Idaho, Utah and Northwest chains added.
"""
import re

BRANDS = [
    ("Dunkin'", r"^DUNKIN"), ("Subway", r"^SUBWAY"), ("McDonald's", r"^MC ?DONALDS"), ("Starbucks", r"^STARBUCK"),
    ("Jimmy John's", r"^JIMMY JOHN"), ("Burger King", r"^BURGER KING"), ("Taco Bell", r"^TACO BELL"),
    ("Potbelly", r"^POTBELLY"), ("Wingstop", r"^WING ?STOP"), ("Chipotle", r"^CHIPOTLE"), ("Popeyes", r"^POPEYE"),
    ("Wendy's", r"^WENDYS"), ("Panda Express", r"^PANDA EXPRESS"), ("White Castle", r"^WHITE CASTLE"),
    ("Chick-fil-A", r"^CHICK FIL"), ("Domino's", r"^DOMINO"), ("Jersey Mike's", r"^JERSEY MIKE"),
    ("Panera Bread", r"^PANERA"), ("Jet's Pizza", r"^JETS PIZZA"), ("Little Caesars", r"^LITTLE CAESAR"),
    ("Papa John's", r"^PAPA JOHN"), ("KFC", r"^KFC|^KENTUCKY FRIED"), ("Tropical Smoothie Cafe", r"^TROPICAL SMOOTHIE"),
    ("Buffalo Wild Wings", r"^BUFFALO WILD"), ("Five Guys", r"^FIVE GUYS"), ("Raising Cane's", r"^RAISING CANE"),
    ("Portillo's", r"^PORTILLO"), ("Auntie Anne's", r"^AUNTIE ANNE"), ("Qdoba", r"^QDOBA"),
    ("Noodles & Company", r"^NOODLES (?:AND )?CO(?:MPANY)?\b"), ("Smoothie King", r"^SMOOTHIE KING"), ("Firehouse Subs", r"^FIREHOUSE SUB"),
    ("IHOP", r"^IHOP"), ("Denny's", r"^DENNYS"), ("Sonic", r"^SONIC DRIVE|^SONIC$"), ("Insomnia Cookies", r"^INSOMNIA COOKIE"),
    ("Crumbl", r"^CRUMBL"), ("Dairy Queen", r"^DAIRY QUEEN|^DQ GRILL|^DQ$"), ("Baskin-Robbins", r"^BASKIN"), ("Krispy Kreme", r"^KRISPY KREME"),
    ("Chuck E. Cheese", r"^CHUCK E CHEESE"), ("Rosati's", r"^ROSATI"), ("Nothing Bundt Cakes", r"^NOTHING BUNDT"),
    ("Hooters", r"^HOOTERS"), ("Cheesecake Factory", r"^CHEESECAKE FACTORY"), ("P.F. Chang's", r"^P ?F CHANG"), ("Maggiano's", r"^MAGGIANO"),
    ("Ruth's Chris", r"^RUTHS CHRIS"), ("Morton's", r"^MORTONS THE STEAK|^MORTONS STEAK"), ("Steak 'n Shake", r"^STEAK N SHAKE"),
    ("Applebee's", r"^APPLEBEE"), ("Chili's", r"^CHILIS"), ("Olive Garden", r"^OLIVE GARDEN"), ("Red Lobster", r"^RED LOBSTER"),
    ("Jamba", r"^JAMBA"), ("Cinnabon", r"^CINNABON"), ("Pizza Hut", r"^PIZZA HUT"), ("Arby's", r"^ARBYS"),
    ("Checkers", r"^CHECKERS DRIVE|^CHECKERS AND RALLY|^CHECKERS$"), ("MOD Pizza", r"^MOD PIZZA"), ("Tim Hortons", r"^TIM HORTON"),
    ("Peet's Coffee", r"^PEETS"), ("Colectivo", r"^COLECTIVO"), ("Cava", r"^CAVA$|^CAVA (?:MEDITERRANEAN|GRILL)"), ("Blaze Pizza", r"^BLAZE PIZZA"),
    # national chains common in Colorado, and Colorado's own
    ("Culver's", r"^CULVER"), ("Taco John's", r"^TACO JOHN"), ("Caribou Coffee", r"^CARIBOU COFFEE|^CARIBOU$"),
    ("Scooter's Coffee", r"^SCOOTERS COFFEE"), ("Dutch Bros", r"^DUTCH BRO"), ("7 Brew", r"^7 BREW"), ("The Human Bean", r"^(?:THE )?HUMAN BEAN"),
    ("Black Rock Coffee", r"^BLACK ROCK COFFEE"), ("Ziggi's Coffee", r"^ZIGGIS"), ("Dazbog Coffee", r"^DAZBOG"),
    ("Texas Roadhouse", r"^TEXAS ROADHOUSE"), ("Famous Dave's", r"^FAMOUS DAVE"), ("Red Robin", r"^RED ROBIN"),
    ("Freddy's", r"^FREDDYS FROZEN|^FREDDYS STEAKBURGER"), ("Papa Murphy's", r"^PAPA MURPH"), ("Marco's Pizza", r"^MARCOS PIZZA"),
    ("Cracker Barrel", r"^CRACKER BARREL"), ("Outback Steakhouse", r"^OUTBACK STEAK"), ("LongHorn Steakhouse", r"^LONGHORN STEAK"),
    ("Cold Stone Creamery", r"^COLD STONE"), ("Golden Corral", r"^GOLDEN CORRAL"),
    ("Old Chicago", r"^OLD CHICAGO$|^OLD CHICAGO (?:PASTA|PIZZA|TAPROOM)"), ("Rock Bottom", r"^ROCK BOTTOM"),
    ("Einstein Bros. Bagels", r"^EINSTEIN BRO"), ("Quiznos", r"^QUIZNO"), ("Fazoli's", r"^FAZOLI"), ("Dickey's Barbecue Pit", r"^DICKEYS"),
    ("HuHot Mongolian Grill", r"^HUHOT"), ("Blimpie", r"^BLIMPIE"), ("Dave's Hot Chicken", r"^DAVES HOT CHICKEN"), ("Sbarro", r"^SBARRO"),
    ("Great Harvest", r"^GREAT HARVEST"), ("Teriyaki Madness", r"^TERIYAKI MADNESS"), ("First Watch", r"^FIRST WATCH"),
    ("TGI Fridays", r"^TGI FRIDAY"), ("Mooyah", r"^MOOYAH"), ("Charleys Cheesesteaks", r"^CHARLEYS"), ("Smashburger", r"^SMASHBURGER"),
    ("Hunt Brothers Pizza", r"^HUNT BROTHERS"), ("Hot Stuff Pizza", r"^HOT STUFF"), ("Krispy Krunchy Chicken", r"^KRISPY KRUNCHY"),
    ("Cheba Hut", r"^CHEBA HUT"), ("MrBeast Burger", r"^MR ?BEAST"), ("It's Just Wings", r"^ITS JUST WINGS"), ("7-Eleven", r"^7 ELEVEN"),
    ("Casey's", r"^CASEYS"), ("Pizza Ranch", r"^PIZZA RANCH"), ("Hardee's", r"^HARDEES"), ("Carl's Jr.", r"^CARLS JR"),
    ("Jack in the Box", r"^JACK IN THE BOX"), ("Del Taco", r"^DEL TACO"), ("Whataburger", r"^WHATABURGER"), ("In-N-Out Burger", r"^IN N OUT"),
    ("Café Rio", r"^CAFE RIO"), ("Costa Vida", r"^COSTA VIDA"), ("Cafe Yumm!", r"^CAFE YUMM"), ("Waffle House", r"^WAFFLE HOUSE"),
    ("Perkins", r"^PERKINS (?:RESTAURANT|BAKERY|AMERICAN|FAMILY)|^PERKINS$"), ("Bob Evans", r"^BOB EVANS"), ("Black Bear Diner", r"^BLACK BEAR DINER"),
    ("Native Grill & Wings", r"^NATIVE GRILL"), ("BJ's Restaurant", r"^BJS RESTAURANT|^BJS BREWHOUSE"), ("Twin Peaks", r"^TWIN PEAKS"),
    ("Kneaders", r"^KNEADERS"), ("Swig", r"^SWIG$"), ("Crave Cookies", r"^CRAVE COOKIE"), ("Paris Baguette", r"^PARIS BAGUETTE"),
    ("Sweetgreen", r"^SWEETGREEN"), ("Torchy's Tacos", r"^TORCHYS"), ("Velvet Taco", r"^VELVET TACO"), ("Fuzzy's Taco Shop", r"^FUZZYS TACO"),
    ("Slim Chickens", r"^SLIM CHICKENS"), ("Zaxby's", r"^ZAXBY"), ("Bojangles", r"^BOJANGLES"), ("Church's Chicken", r"^CHURCHS (?:TEXAS )?CHICKEN"),
    ("Hooters", r"^HOOTERS"), ("Dairy Queen", r"^DAIRY QUEEN|^DQ GRILL|^DQ$"),
    # Idaho-born, Utah and Northwest chains common in Idaho
    ("Westside Drive-In", r"^WESTSIDE DRIVE IN"), ("Big Jud's", r"^BIG JUDS"), ("Boise Fry Company", r"^BOISE FRY"),
    ("Flying Pie Pizzaria", r"^FLYING PIE"), ("Idaho Pizza Company", r"^IDAHO PIZZA CO"), ("Smoky Mountain Pizzeria Grill", r"^SMOKY MOUNTAIN PIZZ"),
    ("Pizza Pie Cafe", r"^PIZZA PIE CAFE"), ("Chicago Connection", r"^CHICAGO CONNECTION"), ("Wingers", r"^WINGERS"),
    ("Fiiz", r"^FIIZ"), ("Sodalicious", r"^SODALICIOUS"), ("Thomas Hammer", r"^THOMAS HAMMER"), ("Moxie Java", r"^MOXIE JAVA"),
    ("Zip's Drive-In", r"^ZIPS DRIVE|^ZIPS$|^ZIPS RESTAURANT"), ("Taco Time", r"^TACO TIME"), ("Arctic Circle", r"^ARCTIC CIRCLE"),
    ("JB's Restaurant", r"^JBS RESTAURANT|^JBS FAMILY|^JBS$"), ("Shari's", r"^SHARIS"), ("Elmer's", r"^ELMERS (?:RESTAURANT|BREAKFAST)|^ELMERS$"),
    ("Bardenay", r"^BARDENAY"), ("Pita Pit", r"^PITA PIT"), ("Port of Subs", r"^PORT OF SUBS"), ("Cafe Zupas", r"^CAFE ZUPAS|^ZUPAS"),
    ("Waffle Love", r"^WAFFLE LOVE"), ("Dirty Dough", r"^DIRTY DOUGH"), ("Godfather's Pizza", r"^GODFATHERS PIZZA"), ("Figaro's Pizza", r"^FIGAROS"),
    ("Pizza Factory", r"^PIZZA FACTORY"), ("Round Table Pizza", r"^ROUND TABLE PIZZA"), ("Mountain Mike's Pizza", r"^MOUNTAIN MIKES PIZZA"),
    ("Abby's Legendary Pizza", r"^ABBYS LEGENDARY|^ABBYS PIZZA"), ("Westside Pizza", r"^WESTSIDE PIZZA"), ("Sizzler", r"^SIZZLER"),
    ("Fuddruckers", r"^FUDDRUCKERS"), ("Reed's Dairy", r"^REEDS DAIRY"), ("Barbacoa", r"^BARBACOA$"), ("Bajio", r"^BAJIO"),
    ("Burgerville", r"^BURGERVILLE"), ("Jimmy's Egg", r"^JIMMYS EGG"), ("Kneaders", r"^KNEADERS"), ("Paradise Bakery", r"^PARADISE BAKERY"),
    ("Nekter Juice Bar", r"^NEKTER"), ("Cafe Rio", r"^CAFE RIO"), ("Chapala", r"^CHAPALA"), ("Jalapeno's", r"^JALAPENOS (?:MEXICAN|BAR)"),
    ("Pizza Hut Express", r"^PIZZA HUT EXPRESS"), ("Blue Sky Bagels", r"^BLUE SKY BAGEL"), ("Java", r"^JAVA ON SHERMAN|^JAVA ON FOURTH"),
    ("Dutch Bros", r"^DUTCH BRO"), ("Sonic", r"^SONIC DRIVE|^SONIC$"), ("Maverik", r"^MAVERIK"), ("Stinker Stations", r"^STINKER"),
    ("Jacksons", r"^JACKSONS FOOD|^JACKSONS$"), ("Common Cents", r"^COMMON CENTS"), ("Love's", r"^LOVES TRAVEL"),
]
_C = [(b, re.compile(p)) for b, p in BRANDS]

# distinctive brands also recognized mid-name ("HALE FAMILY MCDONALDS", "SAII BABA DUNKIN")
_ANYWHERE = [(b, re.compile(p)) for b, p in [("McDonald's", r"\bMC ?DONALDS\b"), ("Dunkin'", r"\bDUNKIN\b"), ("Starbucks", r"\bSTARBUCKS\b"),
             ("Wingstop", r"\bWING ?STOP\b"), ("Culver's", r"\bCULVERS\b"), ("Popeyes", r"\bPOPEYES\b"), ("Chipotle", r"\bCHIPOTLE\b"),
             ("Jimmy John's", r"\bJIMMY JOHNS\b"), ("Taco Bell", r"\bTACO BELL\b")]]


def brand_of(nkey, *more):
    """Brand from the display name, else from Overture's brand label."""
    keys = [k for k in [nkey] + [m for m in more if isinstance(m, str)] if isinstance(k, str)]
    for k in keys:
        for part in [k or ""] + [p.strip() for p in (k or "").split("/")]:
            for b, p in _C:
                if p.search(part):
                    return b
    for k in keys:
        for b, p in _ANYWHERE:
            if p.search(k or ""):
                return b
    return None
