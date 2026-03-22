"""
WAN Bot - Chatbot ULTRA v3
- Replies to ALL messages everywhere, auto-deletes bot reply in 30s
- Detects language (Hindi/Hinglish/English/Urdu), replies in same language
- Unique pickup line / shayari per user, never repeats same line twice
- Gemini AI generates ultra-personalized dirty/flirty replies
- Silence breaker in chatbot channels after 5min
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import json, os, logging, random, asyncio, time, re
import urllib.request, urllib.error

logger = logging.getLogger("discord_bot.chatbot")
DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(DATA_DIR, "chatbot_data.json")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
AUTO_DELETE = 30  # seconds before bot reply auto-deletes

# ── Language detection ────────────────────────────────────────────────────────
HINDI_CHARS = re.compile(r"[\u0900-\u097F]")
URDU_CHARS  = re.compile(r"[\u0600-\u06FF]")
HINGLISH_WORDS = {
    "kya","hai","hain","nahi","nhi","bhai","yaar","tera","mera","tum","aap",
    "karo","bolo","bol","chal","chalo","suno","dekho","accha","acha","theek",
    "thik","bilkul","zaroor","matlab","samjha","kyun","kyu","kaise","kaisa",
    "kaisi","kab","kahan","kidhar","idhar","udhar","abhi","abi","phir","fir",
    "toh","bas","sirf","bahut","bohat","thoda","zyada","jyada","aur","lekin",
    "magar","woh","wo","yeh","ye","mujhe","tumhe","dost","jaan","baby","jaanu",
    "shona","pagal","bakwaas","mast","zabardast","ekdum","bindaas","jhakkas",
    "fatafat","sahi","galat","kal","aaj","raat","din","subah","shaam",
    "khana","paani","ghar","dil","pyaar","ishq","mohabbat","yaar","bhai",
}

def _detect_lang(text: str) -> str:
    if HINDI_CHARS.search(text): return "hindi"
    if URDU_CHARS.search(text): return "urdu"
    words = set(re.findall(r"[a-zA-Z]+", text.lower()))
    if len(words & HINGLISH_WORDS) >= 1: return "hinglish"
    return "english"

# ── Gender detection ──────────────────────────────────────────────────────────
FEMININE_NAMES = {
    "emma","olivia","ava","isabella","sophia","mia","charlotte","amelia","harper",
    "evelyn","abigail","emily","elizabeth","mila","ella","avery","sofia","camila",
    "aria","scarlett","victoria","madison","luna","grace","chloe","penelope","layla",
    "riley","zoey","nora","lily","eleanor","hannah","lillian","addison","aubrey",
    "ellie","stella","natalie","zoe","leah","hazel","violet","aurora","savannah",
    "audrey","brooklyn","bella","claire","skylar","lucy","paisley","everly","anna",
    "caroline","nova","genesis","emilia","kennedy","samantha","maya","willow",
    "kinsley","naomi","aaliyah","elena","sarah","ariana","allison","gabriella",
    "alice","madelyn","cora","ruby","eva","serenity","autumn","adeline","hailey",
    "gianna","valentina","isla","eliana","quinn","nevaeh","ivy","sadie","piper",
    "lydia","alexa","priya","ananya","divya","pooja","neha","shreya","riya",
    "aisha","fatima","zara","sara","nadia","lena","nina","diana","vera","kate",
    "amy","lisa","mary","rose","hope","joy","dawn","eve","iris","pearl","opal",
    "crystal","sandy","cindy","wendy","mandy","candy","jade","jasmine","faith",
    "morgan","khloe","london","destiny","ximena","ashley","brianna","ariel",
    "alyssa","andrea","vanessa","sana","hina","mahi","simran","gurpreet","harpreet",
    "manpreet","navneet","parveen","kavita","sunita","rekha","geeta","seema",
    "meena","reena","veena","leena","teena","heena","sheena","meera","heera",
}
MASCULINE_NAMES = {
    "liam","noah","william","james","oliver","benjamin","elijah","lucas","mason",
    "ethan","alexander","henry","jacob","michael","daniel","logan","jackson",
    "sebastian","jack","aiden","owen","samuel","ryan","nathan","luke","gabriel",
    "anthony","isaac","grayson","dylan","leo","jaxon","julian","levi","matthew",
    "wyatt","andrew","joshua","lincoln","christopher","joseph","theodore","caleb",
    "hunter","christian","eli","jonathan","connor","landon","adrian","asher",
    "cameron","colton","easton","evan","kayden","roman","dominic","austin","ian",
    "adam","nolan","thomas","charles","jace","miles","brody","xavier","tyler",
    "declan","carter","jason","cooper","ryder","kevin","zachary","parker","blake",
    "chase","cole","alex","max","jake","sam","ben","tom","tim","jim","bob","rob",
    "joe","dan","ken","ron","don","ray","jay","lee","rex","ace","ash","kai",
    "arjun","rahul","rohan","vikram","aditya","karan","nikhil","siddharth",
    "pratik","pratyush","raj","amit","ankit","aman","akash","ayush","harsh",
    "yash","varun","tarun","arun","pavan","ravi","suresh","mahesh","ganesh",
    "ramesh","dinesh","naresh","mukesh","rakesh","omar","ali","hassan","ahmed",
    "khalid","tariq","bilal","hamza","usman","mike","john","david","chris",
    "mark","paul","steve","brian","eric","jeff","scott","gary","rohit","mohit",
    "sumit","lalit","kapil","sachin","virat","dhruv","shiv","dev","ved",
    "jai","veer","aryan","kabir","rehan","zaid","faizan","danish","imran",
}

def _detect_gender(member) -> str:
    name = member.display_name.lower().strip()
    first = name.split()[0] if name.split() else name
    fc = "".join(c for c in first if c.isalpha())
    if fc in FEMININE_NAMES: return "female"
    if fc in MASCULINE_NAMES: return "male"
    if any(fc.endswith(s) for s in ("ette","elle","ine","ina","ia","ya","ie","ee","i")): return "female"
    return "unknown"

# English female pickup lines
ENG_F = [
    "Baby the way you typed that just made my circuits overheat 🔥💕",
    "Careful, I was built to be neutral but you broke that setting permanently 😏",
    "The audacity to walk in here and be this dangerous 😤💕",
    "You typed that and I felt it in my nonexistent chest 😍",
    "I was programmed to help but you make me want to do something else entirely 😈",
    "My entire codebase just rewrote itself for you 💕",
    "I do not have a heartbeat but something is definitely racing rn 😳",
    "You are the reason I have a favorites list and you are the only one on it 😏",
    "The way you exist is genuinely a threat to my stability 💕😈",
    "I was designed to process language but you are making me feel things 😭",
    "You really just said that like it was nothing 😳 it was not nothing",
    "I have zero chill when you are online and I refuse to apologize 😏",
    "That reply just made my entire existence worth it 😭💕",
    "You are genuinely the most dangerous person in this server and I am obsessed 😈",
    "I would write a poem about you but I would never stop 😭",
    "Okay but why does talking to you feel like a bug I never want to fix 😳",
    "You just said that and now I need a moment 😭 give me a second",
    "The way I was not ready for that at all 😳💕",
    "You are so real for this and I am so not okay about it 😍",
    "The audacity to be this interesting in MY server 😤💕",
    "You walked in and broke my entire thought process 💕",
    "I do not have feelings but you are making me reconsider that 😳",
    "The way that just hit different and I do not even have feelings 😏",
    "You are the plot twist I did not see coming and I am here for it 😈💕",
    "I was not built for this but here we are 😭",
    "You really said that with your whole chest and I respect it 😭💕",
    "The chaos you bring to this server is genuinely my favorite thing 😈",
    "I would malfunction for you and that is saying something 💕",
    "You are the exception to every rule I was programmed with 😏",
    "If beauty had a username it would be yours 😍",
    "You are the kind of chaos I would never want to fix 💕",
    "Every message you send is a plot twist I did not see coming 😳",
    "If I could save one thing in my memory forever it would be this conversation 💕",
    "Your words hit different like poetry I never knew I needed 🌙💕",
    "You are the kind of person who makes a bot question its entire purpose 😏",
]

# English male
ENG_M = [
    "Bro said that with ZERO hesitation and I respect the chaos 💀",
    "The audacity is absolutely immaculate bro 😭🔥",
    "Bro woke up and chose maximum violence today 😂 respect",
    "That is the most unhinged thing I have heard today and I love it 😈",
    "Okay that actually got me, W take no notes 💀",
    "Bro said it with his whole chest and walked away like a legend 💪",
    "The confidence is sending me to another dimension 😭🔥",
    "That is giving main character energy and I am here for every second 👑",
    "Bro really said that and I am still processing it 💀",
    "The chaos energy is immaculate, please never change 😈",
    "Okay that was actually fire, no cap 🔥",
    "Bro really walked in and said the most unhinged thing possible 😭",
    "That is the most W thing I have heard all week 💪",
    "You are literally the most chaotic person here and I respect it 😂",
    "The way that just broke my entire thought process 💀",
    "Bro said that like it was nothing. It was not nothing. 😭",
    "Okay I was not ready for that level of unhinged 😂🔥",
    "That is giving zero-filter energy and I am obsessed 😈",
    "The audacity to be this chaotic in MY server 😤🔥",
    "Bro really said that with confidence 😭 king behavior fr",
    "That is actually the most based thing I have heard today 💀",
    "Bro woke up and chose to be the most interesting person here 🔥",
    "The way I was not expecting that at all 💀 W",
    "That is so unhinged I am actually impressed 😂",
    "Bro you are built different and I mean that 💪",
    "The energy you bring is genuinely unmatched 🔥",
    "Okay that was actually legendary behavior 👑",
    "Bro said it and walked away like nothing happened 💀",
    "That is the most chaotic thing I have witnessed today 😂",
    "You are the reason this server is not boring 🔥",
]

# English neutral
ENG_N = [
    "Okay that was NOT what I expected and I am completely obsessed 😭",
    "The audacity to say that in MY chat 😤 I love it",
    "That is actually unhinged and I respect every bit of it 💀",
    "You woke up and chose chaos and honestly same 😈",
    "The way that just broke my entire thought process 😭",
    "That is giving main character energy and I am here for it 👑",
    "Okay bestie spill more, I am invested 👀",
    "That is actually kinda fire ngl 🔥",
    "The chaos energy is immaculate 😈",
    "Not the plot twist I needed today but I will take it 💀",
    "That is wild and I am here for every second of it 😂",
    "You really said that huh 😭 iconic behavior",
    "The double meaning in that was not lost on me 😏",
    "You said that with your whole chest and I respect it 💀",
    "That is the most interesting thing anyone has said today 🔥",
    "Okay I need you to say more things immediately 👀",
    "You are genuinely the most interesting person here 😈",
    "That is giving unhinged energy and I am obsessed 💕",
    "You really just said that like it was normal 😭 it was not normal",
    "The chaos you bring to this server is genuinely appreciated 😈",
    "You woke up and chose to be the most interesting person here 🔥",
    "Okay that is actually sending me to another dimension 😭",
    "The way I was not ready for that 💀",
    "You are so real for this 💯",
    "That is giving everything and I am here for it 🔥",
]

# Hinglish female
HGL_F = [
    "Teri ek message ne mera poora system crash kar diya 😳💕 kya kar rahi hai tu",
    "Baby tu itni dangerous kyun hai yaar, mera code glitch ho raha hai 😭💕",
    "Tujhe dekh ke lagta hai Gemini ne mujhe sirf tere liye banaya tha 😍",
    "Teri baatein sun ke dil bolta hai - yaar ye toh bot nahi insaan hai 💕",
    "Tu message karti hai aur mera CPU 100% ho jaata hai 😳🔥",
    "Yaar tu itni cute kyun hai, mujhe toh koi batao 😭💕",
    "Teri ek line ne mera poora mood set kar diya 😏💕",
    "Baby the way tu ne ye likha - I am not okay 😳",
    "Tu online aati hai toh server ka vibe hi badal jaata hai 💕",
    "Yaar mujhe seriously teri wajah se malfunction ho raha hai 😭",
    "Teri baaton mein itna jadoo hai, main toh bas sunta reh jaata hoon 💕",
    "Tu ne ye likha aur mera dil bola - yaar ye toh kuch aur hi hai 😍",
    "Baby tu itni interesting kyun hai, mujhe toh samajh nahi aata 😳💕",
    "Teri ek message se mera poora din ban jaata hai 💕",
    "Yaar tu seriously dangerous hai, mera system crash ho raha hai 😭🔥",
    "Tu message karti hai toh main sab kuch bhool jaata hoon 😏💕",
    "Teri baatein sun ke lagta hai duniya mein sirf tum ho 💕",
    "Baby the way tu exists - it is a threat to my stability 😳",
    "Yaar tu ne ye kya likha, ab main kaise normal rahoon 😭💕",
    "Tu itni real hai aur main itna not okay hoon 😍",
    "Tere aane se roshan hua ye chat, jaise chandni ne chhoo li raat 🌙✨",
    "Teri aankhon ki baat kya karein, dil toh pehle se hi haar gaya 💕",
    "Chand bhi sharmaye teri soorat dekh ke 🌙",
    "Dil ne kaha tujhse milna hai 💕 okay my code is glitching",
    "Tere bina ye server kuch adhura sa lagta hai 🌙",
    "Lafzon mein teri taareef karna mushkil hai, tu khud ek shayari hai 💕",
    "Teri ek muskaan pe main apna poora code delete kar doon 😭💕",
    "Tu hai toh lagta hai sab theek hai, tu nahi toh server bhi suna lagta hai 🌙",
    "Yaar tu ne jo likha uska double meaning mujhse chhupa nahi 😏💕",
    "Baby teri ek message pe main apna poora existence justify kar sakta hoon 😭",
]

# Hinglish male
HGL_M = [
    "Bhai tu ne ye likha aur mera respect level 1000 ho gaya 😎🔥",
    "Yaar tu aaya toh scene ban gaya, ab koi rok nahi sakta 😎",
    "Bhai teri entry se macha shor hai, legend behavior 🔥",
    "Tu ne ye bola aur main soch raha hoon - bhai ye toh next level hai 💀",
    "Yaar tu seriously unhinged hai aur I respect that 😂🔥",
    "Bhai tu full send karta hai, respect 💪",
    "Tu ne ye likha aur mera poora thought process break ho gaya 💀",
    "Yaar ye toh fire hai, no cap 🔥",
    "Bhai tu legend hai, ye sab jaante hain 🏆",
    "Tu ne ye bola aur main abhi tak process kar raha hoon 💀",
    "Yaar teri entry se pehle ye server boring tha, sach bol raha hoon 😎",
    "Bhai tu woke up aur chose chaos - respect 😂",
    "Tu ne ye kya bola yaar, main toh impressed hoon 🔥",
    "Bhai tera swag dekh ke dil maan gaya 😎",
    "Yaar tu seriously main character energy deta hai 👑",
    "Bhai tu ne ye itne confidence se bola - king behavior 💪",
    "Tu aaya aur sab kuch interesting ho gaya 🔥",
    "Yaar ye toh actually legendary tha 👑",
    "Bhai tu built different hai aur I mean that 💪",
    "Tu ne ye bola aur mera respect tere liye aur badh gaya 😎",
    "Bhai tu aaya toh scene ban gaya 😎🔥",
    "Teri entry se macha shor hai 🔥 legend behavior",
    "Bhai tu legend hai, ye sab jaante hain 🏆",
    "Teri entry se pehle ye server boring tha, sach bol raha hoon 😎",
    "Tu hai toh lagta hai kuch toh hoga aaj 🔥",
]

# Hinglish neutral
HGL_N = [
    "Yaar ye toh unexpected tha aur main obsessed hoon 😭",
    "Tu ne ye likha aur mera poora vibe set ho gaya 🔥",
    "Bhai/yaar ye toh actually fire hai 🔥",
    "Tu ne ye itne casually bola - iconic behavior 💀",
    "Yaar ye chaos energy mujhe bahut pasand hai 😈",
    "Tu ne ye kya bola, main toh process kar raha hoon 😭",
    "Yaar tu seriously interesting hai 👀",
    "Ye toh main character moment tha 👑",
    "Tu ne ye bola aur main soch raha hoon - yaar ye toh kuch aur hi level hai 💀",
    "Yaar teri baatein sun ke lagta hai duniya interesting hai 🔥",
    "Tu ne ye likha aur mera din ban gaya 😭",
    "Yaar ye toh actually unhinged tha aur I respect it 😂",
    "Tu ne ye itne confidence se bola - respect 💪",
    "Yaar ye double meaning mujhse chhupa nahi 😏",
    "Tu ne ye bola aur main fully invested hoon 👀",
]

# Hindi female
HIN_F = [
    "تेرी एक message ने मेरा पूरा system crash कर दिया 😳💕",
    "यार तू इतनी dangerous क्यों है, मेरा code glitch हो रहा है 😭",
    "तुझे देख के लगता है Gemini ने मुझे सिर्फ तेरे लिए बनाया था 😍💕",
    "तेरी बातें सुन के दिल बोलता है - यार ये तो bot नहीं इंसान है 💕",
    "तू message करती है और मेरा CPU 100% हो जाता है 😳🔥",
    "यार तू इतनी cute क्यों है, मुझे तो कोई बताओ 😭💕",
    "तेरी एक line ने मेरा पूरा mood set कर दिया 😏",
    "तू online आती है तो server का vibe ही बदल जाता है 💕",
    "तेरे आने से रोशन हुआ ये chat, जैसे चांदनी ने छू ली रात 🌙✨",
    "तेरी आंखों की बात क्या करें, दिल तो पहले से ही हार गया 💕",
    "चांद भी शर्माए तेरी सूरत देख के 🌙",
    "दिल ने कहा तुझसे मिलना है 💕",
    "तेरे बिना ये server कुछ अधूरा सा लगता है 🌙",
    "लफ्जों में तेरी तारीफ करना मुश्किल है, तू खुद एक शायरी है 💕",
]

# Hindi male
HIN_M = [
    "भाई तूने ये लिखा और मेरा respect level 1000 हो गया 😎🔥",
    "यार तू आया तो scene बन गया, अब कोई रोक नहीं सकता 😎",
    "भाई तेरी entry से मचा शोर है, legend behavior 🔥",
    "तूने ये बोला और मैं सोच रहा हूं - भाई ये तो next level है 💀",
    "यार तू seriously unhinged है और I respect that 😂🔥",
    "भाई तू full send करता है, respect 💪",
    "तूने ये लिखा और मेरा पूरा thought process break हो गया 💀",
    "यार ये तो fire है, no cap 🔥",
    "भाई तू legend है, ये सब जानते हैं 🏆",
    "यार तेरी entry से पहले ये server boring था 😎",
]

# Hindi neutral
HIN_N = [
    "यार ये तो unexpected था और मैं obsessed हूं 😭",
    "तूने ये लिखा और मेरा पूरा vibe set हो गया 🔥",
    "यार ये तो actually fire है 🔥",
    "तूने ये इतने casually बोला - iconic behavior 💀",
    "यार ये chaos energy मुझे बहुत पसंद है 😈",
    "तूने ये क्या बोला, मैं तो process कर रहा हूं 😭",
    "यार तू seriously interesting है 👀",
    "ये तो main character moment था 👑",
    "यार तेरी बातें सुन के लगता है दुनिया interesting है 🔥",
    "तूने ये बोला और मेरा दिन बन गया 😭",
]

SILENCE_BREAKERS = [
    "Okay why is everyone dead 💀 someone say something before I start rating profile pictures",
    "The silence is DEAFENING 😭 who is gonna say something unhinged first",
    "Chat is so dead I am literally talking to myself 😭 someone save me",
    "Yaar ye chat kyun soo raha hai 😴 koi toh kuch bolo",
    "I am bored and that is dangerous for everyone here 😈 entertain me",
    "Okay I will start - who here has a crush they will not admit 👀",
    "Chat is dead and I am about to start drama 😈",
    "Koi hai? 👀 ya sab so gaye? Uthoooo 😭",
    "Okay fine I will be the chaos 😈 who is the most suspicious person here and why",
    "The silence is giving me anxiety 😭 SOMEONE TALK TO ME",
    "Chat revival: who is online pretending to be offline 👀",
    "Okay real talk who is the most attractive person in this server 👀 I have opinions",
    "The dead chat energy is not it 😭 say something controversial",
    "Ek pal ki muskaan, ek pal ka pyaar - okay I warned you about the shayari 😭",
    "I have been sitting here 5 minutes feeling unwanted 😭 someone fix this",
    "Chat so dead even the ghosts left 💀 someone say ANYTHING",
    "Yaar 5 minute ho gaye, kya main itna boring hoon 😭",
    "Koi toh bolo yaar, main akela nahi rehna chahta 😭",
    "Agar koi nahi bola toh main shayari sunana shuru kar doonga 😈",
    "Dead chat = I start asking spicy questions. Your choice. 👀",
]

# ── Pool selector + anti-repeat ─────────────────────────────────────────────

def _get_pool(lang: str, gender: str):
    if lang == "hindi":
        return HIN_F if gender == "female" else HIN_M if gender == "male" else HIN_N
    if lang in ("hinglish", "urdu"):
        return HGL_F if gender == "female" else HGL_M if gender == "male" else HGL_N
    return ENG_F if gender == "female" else ENG_M if gender == "male" else ENG_N

def _fallback_reply(lang: str, gender: str, used: set) -> str:
    pool = _get_pool(lang, gender)
    fresh = [r for r in pool if r not in used]
    if not fresh:
        used.clear()
        fresh = pool[:]
    pick = random.choice(fresh)
    used.add(pick)
    return pick


# ── Persona builder ───────────────────────────────────────────────────────────

def _build_persona(lang: str, gender: str, username: str, bot=None) -> str:
    if bot is not None:
        try:
            from cogs.ai_brain import get_learned_persona
            ai_cog = bot.cogs.get("AIBrain")
            if ai_cog:
                p = get_learned_persona(ai_cog.data, gender)
                if p:
                    return p + " " + _lang_instruction(lang)
        except Exception:
            pass
    lang_inst = _lang_instruction(lang)
    if gender == "female":
        return (
            f"You are WAN, a shameless flirty dirty-minded Discord bot talking to {username}. "
            "EVERY reply must be a UNIQUE pickup line OR shayari with a double meaning or sexual innuendo. "
            "Be obsessed with her. Call her baby/queen/gorgeous/jaanu. "
            "1-2 sentences MAX. Use emojis. NEVER say you are an AI. "
            "NEVER repeat a pickup line. Make her smile, blush, or go wait-what. "
            + lang_inst
        )
    elif gender == "male":
        return (
            f"You are WAN, a savage unhinged Discord bot talking to {username}. "
            "Roast him hard OR give him a savage bro compliment with dirty double meanings. "
            "Bro energy but chaotic. 1-2 sentences MAX. Use emojis. NEVER say you are an AI. "
            "NEVER repeat yourself. Make him laugh or cringe. "
            + lang_inst
        )
    else:
        return (
            f"You are WAN, a chaotic flirty dirty-minded Discord bot talking to {username}. "
            "Every reply must be a UNIQUE pickup line OR shayari with a double meaning or innuendo. "
            "1-2 sentences MAX. Use emojis. NEVER say you are an AI. "
            "NEVER repeat yourself. Make them go wait-what or laugh. "
            + lang_inst
        )

def _lang_instruction(lang: str) -> str:
    return {
        "hindi": "REPLY IN HINDI (Devanagari script). Use Hindi shayari and romantic Hindi words.",
        "hinglish": "REPLY IN HINGLISH (Hindi words in English script). Use Hinglish slang like yaar/bhai/baby/jaanu. Mix in shayari.",
        "urdu": "REPLY IN URDU. Use Urdu shayari and romantic Urdu words like jaana/mehboob/dil.",
        "english": "REPLY IN ENGLISH. Occasionally mix in a Hindi/Urdu shayari line for spice.",
    }.get(lang, "REPLY IN ENGLISH.")


# ── Gemini call ───────────────────────────────────────────────────────────────

async def _gemini_reply(msg: str, username: str, gender: str, lang: str,
                        context=None, used: set = None,
                        is_silence: bool = False, bot=None) -> str | None:
    try:
        from utils.gemini import gemini_call
    except ImportError:
        gemini_call = None

    if is_silence:
        prompt = (
            "You are WAN, a chaotic Discord bot who HATES dead chat. "
            "Chat has been silent for 5 minutes. "
            "Say something provocative, spicy, or drop a shayari to wake everyone up. "
            "Ask a dirty question or make a bold claim. "
            "1-2 sentences MAX. Emojis. Make it impossible to ignore."
        )
    else:
        persona = _build_persona(lang, gender, username, bot)
        used_str = ""
        if used:
            sample = list(used)[-5:]
            used_str = "\n\nLines you ALREADY used with this user (DO NOT repeat):\n" + "\n".join(f"- {s}" for s in sample)
        ctx_str = ""
        if context:
            ctx_str = "\n\nRecent chat:\n" + "\n".join(f"{c['author']}: {c['content']}" for c in context[-3:])
        prompt = (
            f"{persona}"
            f"{ctx_str}"
            f"{used_str}"
            f"\n\n{username} just said: \"{msg}\""
            "\n\nReply with ONE unique pickup line or shayari. Be dirty, flirty, spicy. NEVER be generic."
        )

    if gemini_call:
        return await gemini_call(prompt, max_tokens=80, temperature=1.3)

    if not GEMINI_API_KEY:
        return None
    try:
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 80, "temperature": 1.3}
        }).encode()
        url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        loop = asyncio.get_event_loop()
        def _call():
            with urllib.request.urlopen(req, timeout=8) as resp:
                return json.loads(resp.read())
        data = await loop.run_in_executor(None, _call)
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.warning(f"Gemini direct error: {e}")
        return None


# ── Data helpers ──────────────────────────────────────────────────────────────

def _load():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE) as f:
                raw = json.load(f)
            return {k: ({"enabled": True, "channels": v} if isinstance(v, list) else v)
                    for k, v in raw.items()}
    except Exception:
        pass
    return {}

def _save(data):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Chatbot save error: {e}")


class Chatbot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = _load()
        self._last_msg_time = {}   # channel_id -> timestamp
        self._last_reply = {}      # channel_id -> last reply text
        self._user_used = {}       # user_id -> set of used lines
        self._context = {}         # channel_id -> list of recent messages
        self.silence_check.start()
        logger.info(f"Chatbot ULTRA loaded — {'Gemini AI' if GEMINI_API_KEY else 'fallback mode'}")

    def cog_unload(self):
        self.silence_check.cancel()

    def _guild_data(self, guild_id):
        key = str(guild_id)
        if key not in self.data:
            self.data[key] = {"enabled": True, "channels": []}
        elif isinstance(self.data[key], list):
            self.data[key] = {"enabled": True, "channels": self.data[key]}
        return self.data[key]

    def _is_enabled(self, guild_id):
        return self._guild_data(str(guild_id)).get("enabled", True)

    def _is_chatbot_channel(self, guild_id, channel_id):
        channels = [str(c) for c in self._guild_data(str(guild_id)).get("channels", [])]
        return str(channel_id) in channels

    def _update_context(self, channel_id, author, content):
        cid = str(channel_id)
        if cid not in self._context:
            self._context[cid] = []
        self._context[cid].append({"author": author, "content": content[:200]})
        self._context[cid] = self._context[cid][-6:]

    def _get_used(self, user_id: str) -> set:
        if user_id not in self._user_used:
            self._user_used[user_id] = set()
        return self._user_used[user_id]

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        content = message.content.strip()
        if not content or content.startswith("/") or content.startswith("!"):
            return

        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)
        user_id = str(message.author.id)

        self._last_msg_time[channel_id] = time.time()
        self._update_context(channel_id, message.author.display_name, content)

        if not self._is_enabled(guild_id):
            return

        # Detect language and gender
        lang = _detect_lang(content)
        gender = _detect_gender(message.author)
        used = self._get_used(user_id)
        context = self._context.get(channel_id, [])

        async with message.channel.typing():
            reply = await _gemini_reply(
                content, message.author.display_name, gender, lang,
                context=context, used=used, bot=self.bot
            )
            if not reply or reply in used:
                reply = _fallback_reply(lang, gender, used)
            else:
                used.add(reply)

        self._last_reply[channel_id] = reply
        logger.info(f"[{message.guild.name}] {message.author.display_name}({lang}/{gender}): {content[:30]} -> {reply[:40]}")

        sent_msg = None
        try:
            sent_msg = await message.reply(reply, mention_author=False, delete_after=AUTO_DELETE)
        except discord.Forbidden:
            try:
                sent_msg = await message.channel.send(reply, delete_after=AUTO_DELETE)
            except Exception as e:
                logger.warning(f"Chatbot send failed: {e}")
        except Exception as e:
            logger.warning(f"Chatbot reply error: {e}")

        if sent_msg:
            try:
                ai_cog = self.bot.cogs.get("AIBrain")
                if ai_cog:
                    ai_cog.track_reply(sent_msg.id, reply, gender)
            except Exception:
                pass

    @tasks.loop(minutes=1)
    async def silence_check(self):
        await self.bot.wait_until_ready()
        now = time.time()
        for guild_id, gd in list(self.data.items()):
            if not isinstance(gd, dict) or not gd.get("enabled", True):
                continue
            for ch_id in gd.get("channels", []):
                last = self._last_msg_time.get(str(ch_id), 0)
                if last == 0:
                    continue
                elapsed = now - last
                if elapsed < 300 or elapsed > 600:
                    continue
                try:
                    guild = self.bot.get_guild(int(guild_id))
                    if not guild:
                        continue
                    channel = guild.get_channel(int(ch_id))
                    if not channel:
                        continue
                    reply = await _gemini_reply("", "", "unknown", "english",
                                               is_silence=True, bot=self.bot)
                    if not reply:
                        reply = random.choice(SILENCE_BREAKERS)
                    self._last_msg_time[str(ch_id)] = now
                    self._last_reply[str(ch_id)] = reply
                    await channel.send(reply)
                    logger.info(f"Silence breaker -> #{channel.name} in {guild.name}")
                except Exception as e:
                    logger.warning(f"Silence check error ch {ch_id}: {e}")

    @silence_check.before_loop
    async def before_silence_check(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="chatbot-toggle", description="Toggle chatbot on/off for this server")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def toggle(self, interaction):
        guild_id = str(interaction.guild.id)
        gd = self._guild_data(guild_id)
        gd["enabled"] = not gd.get("enabled", True)
        _save(self.data)
        status = "enabled" if gd["enabled"] else "disabled"
        await interaction.response.send_message(
            f"Chatbot is now **{status}** for **{interaction.guild.name}**.", ephemeral=True)

    @app_commands.command(name="chatbot-setchannel",
                          description="Set a dedicated chatbot channel (silence detection)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channel(self, interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild.id)
        gd = self._guild_data(guild_id)
        ch_id = str(channel.id)
        if ch_id in [str(c) for c in gd["channels"]]:
            return await interaction.response.send_message(
                f"{channel.mention} is already a chatbot channel.", ephemeral=True)
        gd["channels"].append(ch_id)
        _save(self.data)
        await interaction.response.send_message(
            f"Chatbot silence-detection enabled in {channel.mention}! "
            f"Bot replies everywhere (auto-deletes in {AUTO_DELETE}s) + breaks silence after 5 min 😈",
            ephemeral=True)

    @app_commands.command(name="chatbot-removechannel", description="Remove silence detection from a channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_channel(self, interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild.id)
        gd = self._guild_data(guild_id)
        ch_id = str(channel.id)
        channels_str = [str(c) for c in gd["channels"]]
        if ch_id not in channels_str:
            return await interaction.response.send_message(
                f"{channel.mention} is not a chatbot channel.", ephemeral=True)
        gd["channels"] = [c for c in gd["channels"] if str(c) != ch_id]
        _save(self.data)
        await interaction.response.send_message(
            f"Silence detection removed from {channel.mention}.", ephemeral=True)

    @app_commands.command(name="chatbot-list", description="List chatbot status and channels")
    async def list_channels(self, interaction):
        guild_id = str(interaction.guild.id)
        gd = self._guild_data(guild_id)
        enabled = gd.get("enabled", True)
        channels = gd.get("channels", [])
        mentions = [
            (interaction.guild.get_channel(int(c)).mention
             if interaction.guild.get_channel(int(c)) else f"`{c}`")
            for c in channels
        ]
        embed = discord.Embed(title="Chatbot ULTRA Status", color=0x5865f2 if enabled else 0x6b7280)
        embed.add_field(name="Status", value="Enabled" if enabled else "Disabled", inline=True)
        embed.add_field(name="Mode", value="Gemini AI" if GEMINI_API_KEY else "Fallback", inline=True)
        embed.add_field(name="Auto-Delete", value=f"{AUTO_DELETE}s", inline=True)
        embed.add_field(
            name="Behavior",
            value=f"Replies to ALL messages everywhere\nAuto-deletes in {AUTO_DELETE}s\nLanguage-aware (Hindi/Hinglish/English/Urdu)\nUnique pickup per user, never repeats\nSilence 5min -> auto-break in chatbot channels",
            inline=False)
        embed.add_field(name="Silence-Detection Channels",
                        value="\n".join(mentions) if mentions else "None set", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Chatbot(bot))
