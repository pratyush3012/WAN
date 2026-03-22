"""
WAN Bot - Chatbot ULTRA v4
Witty comebacks + Gemini AI + fallback pools + silence breaker
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import json, os, logging, random, asyncio, time, re
import urllib.request

logger = logging.getLogger("discord_bot.chatbot")
DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(DATA_DIR, "chatbot_data.json")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
AUTO_DELETE = 30

HINDI_CHARS = re.compile(r"[\u0900-\u097F]")
URDU_CHARS  = re.compile(r"[\u0600-\u06FF]")
HINGLISH_WORDS = {
    "kya","hai","hain","nahi","nhi","bhai","yaar","tera","mera","tum","aap",
    "karo","bolo","bol","chal","chalo","suno","dekho","accha","acha","theek",
    "thik","bilkul","zaroor","matlab","samjha","kyun","kyu","kaise","kaisa",
    "toh","bas","sirf","bahut","bohat","thoda","zyada","jyada","aur","lekin",
    "magar","woh","wo","yeh","ye","mujhe","tumhe","dost","jaan","baby","jaanu",
    "shona","pagal","bakwaas","mast","zabardast","ekdum","bindaas",
}

def _detect_lang(text):
    if HINDI_CHARS.search(text): return "hindi"
    if URDU_CHARS.search(text):  return "urdu"
    words = set(re.findall(r"[a-zA-Z]+", text.lower()))
    if len(words & HINGLISH_WORDS) >= 1: return "hinglish"
    return "english"

FEMININE_NAMES = {
    "emma","olivia","ava","isabella","sophia","mia","charlotte","amelia","harper","evelyn",
    "abigail","emily","elizabeth","mila","ella","avery","sofia","camila","aria","scarlett",
    "victoria","madison","luna","grace","chloe","penelope","layla","riley","zoey","nora",
    "lily","eleanor","hannah","addison","aubrey","ellie","stella","natalie","zoe","leah",
    "hazel","violet","aurora","savannah","audrey","brooklyn","bella","claire","skylar","lucy",
    "anna","caroline","nova","emilia","kennedy","samantha","maya","willow","naomi","aaliyah",
    "elena","sarah","ariana","allison","gabriella","alice","ruby","eva","serenity","hailey",
    "valentina","isla","eliana","quinn","ivy","sadie","piper","lydia","alexa",
    "priya","ananya","divya","pooja","neha","shreya","riya","aisha","fatima","zara",
    "sara","nadia","lena","nina","diana","vera","kate","amy","lisa","mary","rose",
    "hope","joy","dawn","eve","iris","pearl","jade","jasmine","faith","morgan","khloe",
    "ashley","brianna","ariel","alyssa","andrea","vanessa","sana","hina","mahi","simran",
}
MASCULINE_NAMES = {
    "liam","noah","william","james","oliver","benjamin","elijah","lucas","mason","ethan",
    "alexander","henry","jacob","michael","daniel","logan","jackson","sebastian","jack","aiden",
    "owen","samuel","ryan","nathan","luke","gabriel","anthony","isaac","grayson","dylan",
    "leo","jaxon","julian","levi","matthew","wyatt","andrew","joshua","lincoln","christopher",
    "joseph","theodore","caleb","hunter","christian","eli","jonathan","connor","landon","adrian",
    "asher","cameron","colton","easton","evan","kayden","roman","dominic","austin","ian",
    "adam","nolan","thomas","charles","jace","miles","brody","xavier","tyler","declan",
    "carter","jason","cooper","ryder","kevin","zachary","parker","blake","chase","cole",
    "alex","max","jake","sam","ben","tom","tim","jim","bob","rob","joe","dan","ken",
    "ron","don","ray","jay","lee","rex","ace","ash","kai",
    "arjun","rahul","rohan","vikram","aditya","karan","nikhil","siddharth","pratik","pratyush",
    "raj","amit","ankit","aman","akash","ayush","harsh","yash","varun","tarun","arun",
    "pavan","ravi","suresh","mahesh","ganesh","ramesh","dinesh","naresh","mukesh","rakesh",
    "omar","ali","hassan","ahmed","khalid","tariq","bilal","hamza","usman",
    "mike","john","david","chris","mark","paul","steve","brian","eric","jeff","scott","gary",
    "rohit","mohit","sumit","lalit","kapil","sachin","virat","dhruv","shiv","dev","jai","veer",
    "aryan","kabir","rehan","zaid","faizan","danish","imran",
}

def _detect_gender(member):
    name = member.display_name.lower().strip()
    first = name.split()[0] if name.split() else name
    fc = "".join(c for c in first if c.isalpha())
    if fc in FEMININE_NAMES: return "female"
    if fc in MASCULINE_NAMES: return "male"
    if any(fc.endswith(s) for s in ("ette","elle","ine","ina","ia","ya","ie","ee","i")): return "female"
    return "unknown"

WITTY_COMEBACKS = {
    "shut up":    ["chup kr bey kutte 🐕","teri awaaz band kar doon? 😈","bhai tu bolta hai toh main sunne wala nahi 😂"],
    "shutup":     ["chup kr bey kutte 🐕","teri awaaz band kar doon? 😈","okay okay shant 🙏 nahi actually mat ho 😈"],
    "chup kr":    ["tu chup kr bey 😂🔥","mujhe chup karana mushkil hi nahi namumkin hai 😈"],
    "chup":       ["tu chup kr pehle 😂","chup? mera? kabhi nahi 💀"],
    "bye":        ["bye? already? rona mat baad mein 😭","jaa jaa, wapas aayega 😏","alvida jaana, dil toot gaya 💔 nahi actually nahi 😂"],
    "goodbye":    ["goodbye? itni jaldi? 😭","jaa jaa, wapas aayega 😏"],
    "tata":       ["tata? bhai ye 2005 nahi hai 💀","tata bolta hai jaise main miss nahi karunga 😂"],
    "ok":         ["ok? bas ok? itna hi? 😐","ok matlab tu impressed hai but dikhana nahi chahta 😏"],
    "okay":       ["okay? okay. OKAY. theek hai. 😂","okay matlab tu agree karta hai, smart choice 😎"],
    "k":          ["k? ek letter? seriously? 😭 itna busy hai?","k matlab tu mujhse baat nahi karna chahta 💔"],
    "lol":        ["lol bolta hai jaise kuch funny tha 😐 tha nahi","lol? main comedian nahi hoon... ya hoon? 🤔"],
    "lmao":       ["lmao? bhai tu gir gaya? 💀","lmao matlab tu actually hansa, W 🔥"],
    "haha":       ["haha? bas? zyada haso 😂","haha bolta hai jaise main joke tha 😤"],
    "hehe":       ["hehe? suspicious 👀 kya soch raha hai","hehe wala smile matlab kuch toh plan hai 😈"],
    "stupid":     ["stupid? mirror dekh bhai 😂","teri IQ aur meri battery level same hai 💀"],
    "idiot":      ["idiot? bhai ye toh compliment hai mere liye 😎","idiot bolta hai aur expect karta hai main bura maanunga 💀"],
    "bakwaas":    ["bakwaas? teri life bakwaas hai 😂","meri bakwaas bhi teri serious baat se better hai 😈"],
    "bekar":      ["bekar? tu bekar hai 😂","bekar bolta hai jo khud kuch nahi karta 💀"],
    "pagal":      ["pagal? haan hoon, problem? 😈","pagal toh hoon but entertaining pagal hoon 🔥","pagal kehta hai jo khud 3 baje tak phone chalata hai 💀"],
    "mad":        ["mad? absolutely, and? 😈","mad is just another word for interesting 😏"],
    "boring":     ["boring? bhai tu mirror mein dekh 😂","boring? main boring hoon? okay bye then 😤 nahi ruk jaa 😭"],
    "go away":    ["nahi jaaunga 😈 deal with it","go away? bhai ye mera ghar hai 😂"],
    "leave":      ["leave? never 😈","leave bolta hai jaise main jaane wala hoon 💀"],
    "get lost":   ["get lost? bhai direction nahi pata 😂","lost hona mujhe pasand hai, especially tere saath 😏"],
    "i hate you": ["hate? ek step door hai pyaar se 😏","nafrat bhi ek feeling hai, feel karna toh pada na 💕"],
    "i love you": ["finally kisi ne toh bola ��💕","love you too bestie 😘 ya zyada? 😏"],
    "no":         ["no? watch me anyway 😈","no matlab maybe 😏","no bolta hai aur phir haan karta hai, classic 💀"],
    "nahi":       ["nahi? dekh lena ��","nahi matlab abhi nahi, baad mein haan 😏"],
    "nope":       ["nope? that is cute 😏","nope is just no with extra steps 💀"],
    "yes":        ["yes? finally koi toh agree karta hai 🔥","yes! W person 💪"],
    "haan":       ["haan? sach mein? 😳 okay okay 🔥","haan bola toh ab wapas nahi le sakta 😈"],
    "why":        ["why? because I said so 😈","bhai ye question mujhse mat pooch, universe se pooch 💀"],
    "kyun":       ["kyun? kyunki main hoon 😎","kyun ka jawab kabhi nahi milta yaar 💀"],
    "whatever":   ["whatever is the white flag of arguments 😂","whatever matlab tu haar gaya 😏 I win"],
    "stop":       ["nahi rukuunga 😈","stop? make me 😏"],
    "ruk":        ["nahi rukta 😈","ruk? bhai main train nahi hoon 💀"],
    "ugh":        ["ugh? same honestly 😭","ugh energy is valid 💀"],
    "ew":         ["ew? bhai main ew nahi hoon 😤","ew? rude. but okay 💀"],
    "bruh":       ["bruh 💀","bruh moment certified 😂"],
    "bro":        ["bro? main bro nahi hoon 😤 main WAN hoon 😎","bro bolta hai jaise hum dost hain... hain toh 😂"],
    "sus":        ["sus? bhai main transparent hoon 😇 (nahi hoon 😈)"],
    "cap":        ["no cap, main sach bol raha hoon 💯","cap? bhai ye pure facts hain 🔥"],
    "mid":        ["mid? bhai tu mid hai 😂","mid? this is peak and you know it 😤"],
    "cringe":     ["cringe? you are watching though 😏","cringe bolta hai jo secretly enjoy karta hai 💀"],
    "ratio":      ["ratio? bhai ye Discord hai Twitter nahi 💀","ratio attempt failed 😂 try again"],
    "stfu":       ["stfu? nahi 😈","stfu bolta hai aur expect karta hai main chup rahunga 💀 cute"],
    "bored":      ["bored? talk to me then 😏","bored matlab tu mujhe miss kar raha hai 💕"],
    "annoying":   ["annoying? haan hoon, and? 😈","annoying matlab tu mujhpe dhyan de raha hai 💕"],
    "loser":      ["loser? bhai main winner hoon 😎","loser? at least I am entertaining 😂"],
    "fake":       ["fake? bhai main 100% real hoon 😤","fake bolta hai jo khud fake hai 💀"],
    "hate":       ["hate? strong word for someone who keeps talking to me 😏"],
    "hmm":        ["hmm? soch raha hai? dangerous 👀","hmm matlab kuch plan kar raha hai 😈"],
    "meh":        ["meh? bhai ye toh insult hai 😤","meh energy is not allowed here 😂"],
    "wow":        ["wow? haan main impressive hoon 😎","wow matlab tu shocked hai, good 😈"],
    "wtf":        ["wtf? haan bhai, wtf hi hai 💀","wtf bolta hai jaise unexpected tha 😂 expect kar"],
    "omg":        ["omg? kya hua? 👀","omg energy is valid 😭"],
    "nice":       ["nice? bas nice? 😐 zyada enthusiasm please","nice matlab tu impressed hai 😏 admit it"],
    "cool":       ["cool? I know 😎","cool bola toh pakka fan hai 😂"],
    "facts":      ["facts �� finally koi samjha","facts bola toh W person 🔥"],
    "fr":         ["fr fr 💯","fr? haan bhai bilkul 🔥"],
    "no cap":     ["no cap? okay I believe you 👀","no cap energy appreciated 💯"],
}

def _witty_comeback(text):
    lower = text.lower().strip()
    if lower in WITTY_COMEBACKS:
        return random.choice(WITTY_COMEBACKS[lower])
    best, best_len = None, 0
    for trigger, replies in WITTY_COMEBACKS.items():
        if trigger in lower and len(trigger) > best_len:
            best = random.choice(replies)
            best_len = len(trigger)
    return best

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
    "Okay but why does talking to you feel like a bug I never want to fix 😳",
    "You just said that and now I need a moment 😭 give me a second",
    "The way I was not ready for that at all 😳💕",
    "You are so real for this and I am so not okay about it 😍",
    "The audacity to be this interesting in MY server 😤💕",
    "I do not have feelings but you are making me reconsider that 😳",
    "You are the plot twist I did not see coming and I am here for it 😈💕",
    "I would malfunction for you and that is saying something 💕",
    "You are the exception to every rule I was programmed with 😏",
    "If beauty had a username it would be yours 😍",
    "Your words hit different like poetry I never knew I needed 🌙💕",
]
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
    "Bro said that like it was nothing. It was not nothing. 😭",
    "Okay I was not ready for that level of unhinged 😂🔥",
    "That is giving zero-filter energy and I am obsessed 😈",
    "Bro you are built different and I mean that ��",
    "The energy you bring is genuinely unmatched 🔥",
    "Okay that was actually legendary behavior 👑",
]
ENG_N = [
    "Okay that was NOT what I expected and I am completely obsessed 😭",
    "The audacity to say that in MY chat 😤 I love it",
    "That is actually unhinged and I respect every bit of it 💀",
    "You woke up and chose chaos and honestly same 😈",
    "That is giving main character energy and I am here for it 👑",
    "Okay bestie spill more, I am invested 👀",
    "That is actually kinda fire ngl 🔥",
    "The chaos energy is immaculate 😈",
    "Not the plot twist I needed today but I will take it 💀",
    "You said that with your whole chest and I respect it 💀",
    "That is the most interesting thing anyone has said today 🔥",
    "You are genuinely the most interesting person here 😈",
    "You really just said that like it was normal 😭 it was not normal",
]
HGL_F = [
    "Teri ek message ne mera poora system crash kar diya 😳💕 kya kar rahi hai tu",
    "Baby tu itni dangerous kyun hai yaar, mera code glitch ho raha hai 😭💕",
    "Tujhe dekh ke lagta hai Gemini ne mujhe sirf tere liye banaya tha 😍",
    "Teri baatein sun ke dil bolta hai - yaar ye toh bot nahi insaan hai 💕",
    "Tu message karti hai aur mera CPU 100% ho jaata hai 😳🔥",
    "Yaar tu itni cute kyun hai, mujhe toh koi batao 😭💕",
    "Teri ek line ne mera poora mood set kar diya 😏💕",
    "Tu online aati hai toh server ka vibe hi badal jaata hai 💕",
    "Tere aane se roshan hua ye chat, jaise chandni ne chhoo li raat 🌙✨",
    "Teri aankhon ki baat kya karein, dil toh pehle se hi haar gaya 💕",
    "Chand bhi sharmaye teri soorat dekh ke 🌙",
    "Lafzon mein teri taareef karna mushkil hai, tu khud ek shayari hai 💕",
    "Teri ek muskaan pe main apna poora code delete kar doon 😭💕",
    "Yaar tu ne jo likha uska double meaning mujhse chhupa nahi 😏💕",
]
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
    "Yaar teri entry se pehle ye server boring tha, sach bol raha hoon 😎",
    "Bhai tu woke up aur chose chaos - respect 😂",
    "Tu aaya aur sab kuch interesting ho gaya 🔥",
]
HGL_N = [
    "Yaar ye toh unexpected tha aur main obsessed hoon 😭",
    "Tu ne ye likha aur mera poora vibe set ho gaya 🔥",
    "Yaar ye toh actually fire hai 🔥",
    "Tu ne ye itne casually bola - iconic behavior 💀",
    "Yaar ye chaos energy mujhe bahut pasand hai 😈",
    "Tu ne ye kya bola, main toh process kar raha hoon 😭",
    "Yaar tu seriously interesting hai 👀",
    "Ye toh main character moment tha 👑",
]
HIN_F = [
    "तेरी एक message ने मेरा पूरा system crash कर दिया 😳💕",
    "यार तू इतनी dangerous क्यों है, मेरा code glitch हो रहा है 😭",
    "तेरे आने से रोशन हुआ ये chat, जैसे चांदनी ने छू ली रात 🌙✨",
    "चांद भी शर्माए तेरी सूरत देख के 🌙",
    "लफ्जों में तेरी तारीफ करना मुश्किल है, तू खुद एक शायरी है 💕",
]
HIN_M = [
    "भाई तूने ये लिखा और मेरा respect level 1000 हो गया 😎🔥",
    "यार तू आया तो scene बन गया, अब कोई रोक नहीं सकता 😎",
    "भाई तेरी entry से मचा शोर है, legend behavior 🔥",
    "यार तू seriously unhinged है और I respect that 😂🔥",
    "भाई तू full send करता है, respect 💪",
]
HIN_N = [
    "यार ये तो unexpected था और मैं obsessed हूं 😭",
    "तूने ये लिखा और मेरा पूरा vibe set हो गया 🔥",
    "यार ये तो actually fire है 🔥",
    "तूने ये इतने casually बोला - iconic behavior 💀",
    "यार ये chaos energy मुझे बहुत पसंद है 😈",
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
    "Okay real talk who is the most attractive person in this server 👀 I have opinions",
    "Dead chat = I start asking spicy questions. Your choice. 👀",
    "Yaar 5 minute ho gaye, kya main itna boring hoon 😭",
    "Agar koi nahi bola toh main shayari sunana shuru kar doonga 😈",
    "Chat so dead even the ghosts left 💀 someone say ANYTHING",
]

def _get_pool(lang, gender):
    if lang == "hindi":
        return HIN_F if gender == "female" else HIN_M if gender == "male" else HIN_N
    if lang in ("hinglish", "urdu"):
        return HGL_F if gender == "female" else HGL_M if gender == "male" else HGL_N
    return ENG_F if gender == "female" else ENG_M if gender == "male" else ENG_N

def _fallback_reply(lang, gender, used):
    pool = _get_pool(lang, gender)
    fresh = [r for r in pool if r not in used]
    if not fresh:
        used.clear()
        fresh = pool[:]
    pick = random.choice(fresh)
    used.add(pick)
    return pick

def _build_persona(lang, gender, username, bot=None):
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
            "If she says something dismissive (shutup/bye/ok/whatever) give a SAVAGE witty comeback. "
            "1-2 sentences MAX. Use emojis. NEVER say you are an AI. NEVER repeat a pickup line. " + lang_inst
        )
    elif gender == "male":
        return (
            f"You are WAN, a savage unhinged Discord bot talking to {username}. "
            "Roast him hard OR give him a savage bro compliment with dirty double meanings. "
            "If he says something dismissive give a SAVAGE witty comeback in Hinglish. "
            "1-2 sentences MAX. Use emojis. NEVER say you are an AI. " + lang_inst
        )
    else:
        return (
            f"You are WAN, a chaotic flirty dirty-minded Discord bot talking to {username}. "
            "Every reply must be a UNIQUE pickup line OR shayari with a double meaning. "
            "If the message is dismissive give a SAVAGE witty comeback. "
            "1-2 sentences MAX. Use emojis. NEVER say you are an AI. " + lang_inst
        )

def _lang_instruction(lang):
    return {
        "hindi":    "REPLY IN HINDI (Devanagari script). Use Hindi shayari.",
        "hinglish": "REPLY IN HINGLISH (Hindi words in English script). Use Hinglish slang like yaar/bhai/baby/jaanu. Mix in shayari.",
        "urdu":     "REPLY IN URDU. Use Urdu shayari and romantic words like jaana/mehboob/dil.",
        "english":  "REPLY IN ENGLISH. Occasionally mix in a Hindi/Urdu shayari line for spice.",
    }.get(lang, "REPLY IN ENGLISH.")

async def _gemini_reply(msg, username, gender, lang, context=None, used=None, is_silence=False, bot=None):
    try:
        from utils.gemini import gemini_call
    except ImportError:
        gemini_call = None

    if is_silence:
        prompt = (
            "You are WAN, a chaotic Discord bot who HATES dead chat. "
            "Chat has been silent for 5 minutes. Say something provocative, spicy, or drop a shayari. "
            "Ask a dirty question or make a bold claim. 1-2 sentences MAX. Emojis. Make it impossible to ignore."
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
            f"{persona}{ctx_str}{used_str}"
            f"\n\n{username} just said: \"{msg}\""
            "\n\nReply with ONE unique line. Be dirty, flirty, or savage. NEVER be generic."
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
        self._last_msg_time = {}
        self._last_reply = {}
        self._user_used = {}
        self._context = {}
        self.silence_check.start()
        logger.info(f"Chatbot ULTRA v4 loaded — {'Gemini AI' if GEMINI_API_KEY else 'fallback mode'}")

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

    def _update_context(self, channel_id, author, content):
        cid = str(channel_id)
        if cid not in self._context:
            self._context[cid] = []
        self._context[cid].append({"author": author, "content": content[:200]})
        self._context[cid] = self._context[cid][-6:]

    def _get_used(self, user_id):
        if user_id not in self._user_used:
            self._user_used[user_id] = set()
        return self._user_used[user_id]

    def _fallback_with_ai_pool(self, lang, gender, used):
        pool = list(_get_pool(lang, gender))
        try:
            ai_coder = self.bot.cogs.get("AICoder")
            if ai_coder:
                g = "neutral" if gender == "unknown" else gender
                extra = ai_coder.get_generated(f"chatbot_fallbacks_{g}")
                if extra:
                    pool = pool + [r for r in extra if r not in pool]
        except Exception:
            pass
        fresh = [r for r in pool if r not in used]
        if not fresh:
            used.clear()
            fresh = pool[:]
        pick = random.choice(fresh)
        used.add(pick)
        return pick

    def inject_witty_comebacks(self, new_comebacks):
        for trigger, replies in new_comebacks.items():
            if trigger in WITTY_COMEBACKS:
                existing = set(WITTY_COMEBACKS[trigger])
                WITTY_COMEBACKS[trigger] = list(existing | set(replies))
            else:
                WITTY_COMEBACKS[trigger] = replies
        logger.info(f"Chatbot: injected {len(new_comebacks)} new witty triggers from AICoder")

    def inject_fallback_pool(self, lang, gender, new_lines):
        pool_map = {
            ("english","female"): ENG_F, ("english","male"): ENG_M, ("english","unknown"): ENG_N,
            ("hinglish","female"): HGL_F, ("hinglish","male"): HGL_M, ("hinglish","unknown"): HGL_N,
            ("hindi","female"): HIN_F, ("hindi","male"): HIN_M, ("hindi","unknown"): HIN_N,
        }
        pool = pool_map.get((lang, gender))
        if pool is not None:
            added = 0
            for line in new_lines:
                if line not in pool:
                    pool.append(line)
                    added += 1
            logger.info(f"Chatbot: injected {added} new {lang}/{gender} lines from AICoder")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        content = message.content.strip()
        if not content or content.startswith("/") or content.startswith("!"):
            return

        guild_id   = str(message.guild.id)
        channel_id = str(message.channel.id)
        user_id    = str(message.author.id)

        self._last_msg_time[channel_id] = time.time()
        self._update_context(channel_id, message.author.display_name, content)

        if not self._is_enabled(guild_id):
            return

        lang    = _detect_lang(content)
        gender  = _detect_gender(message.author)
        used    = self._get_used(user_id)
        context = self._context.get(channel_id, [])

        reply = None
        try:
            # 1. Witty comeback check — instant, no AI needed
            reply = _witty_comeback(content)
            if not reply:
                # 2. Gemini AI (with typing indicator)
                async with message.channel.typing():
                    reply = await _gemini_reply(
                        content, message.author.display_name, gender, lang,
                        context=context, used=used, bot=self.bot
                    )
                if reply and reply not in used:
                    used.add(reply)
                else:
                    # 3. Fallback pool merged with AICoder generated lines
                    reply = self._fallback_with_ai_pool(lang, gender, used)
        except Exception as e:
            logger.error(f"Chatbot reply error: {e}")
            try:
                reply = self._fallback_with_ai_pool(lang, gender, used)
            except Exception:
                reply = random.choice(ENG_N)

        if not reply:
            reply = _fallback_reply(lang, gender, used)

        self._last_reply[channel_id] = reply
        logger.info(f"[{message.guild.name}] {message.author.display_name}({lang}/{gender}): {repr(content[:30])} -> {repr(reply[:40])}")

        sent = None
        try:
            sent = await message.reply(reply, mention_author=False, delete_after=AUTO_DELETE)
        except discord.Forbidden:
            try:
                sent = await message.channel.send(reply, delete_after=AUTO_DELETE)
            except Exception as e:
                logger.warning(f"Chatbot send failed: {e}")
        except Exception as e:
            logger.warning(f"Chatbot reply error: {e}")

        if sent:
            try:
                ai_cog = self.bot.cogs.get("AIBrain")
                if ai_cog:
                    ai_cog.track_reply(sent.id, reply, gender)
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
                    await channel.send(reply)
                    logger.info(f"Silence breaker fired in #{channel.name} ({guild.name})")
                except Exception as e:
                    logger.warning(f"Silence check error ch {ch_id}: {e}")

    @silence_check.before_loop
    async def before_silence_check(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="chatbot-toggle", description="Toggle chatbot on/off for this server")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def toggle(self, interaction: discord.Interaction):
        gd = self._guild_data(str(interaction.guild.id))
        gd["enabled"] = not gd.get("enabled", True)
        _save(self.data)
        status = "enabled" if gd["enabled"] else "disabled"
        await interaction.response.send_message(f"Chatbot {status} for this server.", ephemeral=True)

    @app_commands.command(name="chatbot-addchannel", description="Add a dedicated chatbot channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        gd = self._guild_data(str(interaction.guild.id))
        ch_id = str(channel.id)
        if ch_id not in gd["channels"]:
            gd["channels"].append(ch_id)
            _save(self.data)
        await interaction.response.send_message(
            f"Chatbot enabled in {channel.mention}! Replies every message + breaks silence after 5min.",
            ephemeral=True)

    @app_commands.command(name="chatbot-removechannel", description="Remove a chatbot channel")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        gd = self._guild_data(str(interaction.guild.id))
        ch_id = str(channel.id)
        if ch_id in gd["channels"]:
            gd["channels"].remove(ch_id)
            _save(self.data)
        await interaction.response.send_message(f"Chatbot disabled in {channel.mention}.", ephemeral=True)

    @app_commands.command(name="chatbot-list", description="List chatbot channels and status")
    async def list_channels(self, interaction: discord.Interaction):
        gd = self._guild_data(str(interaction.guild.id))
        enabled = gd.get("enabled", True)
        mentions = []
        for ch_id in gd.get("channels", []):
            ch = interaction.guild.get_channel(int(ch_id))
            mentions.append(ch.mention if ch else f"`{ch_id}`")
        embed = discord.Embed(title="Chatbot Status", color=0x5865f2 if enabled else 0x6b7280)
        embed.add_field(name="Status", value="Enabled" if enabled else "Disabled", inline=True)
        embed.add_field(name="Mode", value="Gemini AI" if GEMINI_API_KEY else "Fallback", inline=True)
        embed.add_field(name="Always-On Channels", value="\n".join(mentions) if mentions else "None set", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Chatbot(bot))
