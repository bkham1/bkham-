import os
import time
import threading
import json
import re
import random
import traceback
import difflib
import sys

try:
    import keep_alive
    keep_alive.keep_alive()
    print("✅ keep_alive شغال بنجاح (سيرفر Flask مفتوح على المنفذ 8080)")
except ImportError:
    print("❌ فشل استيراد ملف keep_alive.py. تأكد من وجوده في نفس مجلد البوت.")
except Exception as e:
    print(f"⚠️ فشل تشغيل keep_alive: {e}")

try:
    import aminodorksfix as amino
    from aminodorksfix.lib.util.exceptions import UnexistentData
except ImportError:
    import amino
    from amino.lib.util.exceptions import UnexistentData

from gtts import gTTS
from threading import Thread as T
from random import choice, sample, randint
from num2words import num2words 

EMAIL ="abosaeg8@gmail.com"
PASSWORD ="foo40k"
API_KEY ="1bd49e6563fb5b744a999b6c050197a9"
PROXY_URL ="http://leAdmcMrn3SIpVEt:6MuHyFW8szSgY1Mz@geo.floppydata.com:10080"

BOT_NAME_AR = "رايس"
BOT_NAME_EN = "Raise"
BOT_ALIASES = {BOT_NAME_AR.lower(), BOT_NAME_EN.lower(), "!رايس", "!raise"}
DEV_UID = "c0784194-8d1f-412d-b700-bf54b8b76904"
DEV_LINK = "http://aminoapps.com/p/ypiy3p2"
DEV_KEYWORDS = ["المطور", "كتشب", "من هو كتشب", "وين حساب كتشب", "من هو المطور", "مطور البوت"]
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
paths = {
    "responses": os.path.join(BASE_DIR, "ردود.txt"),
    "unclear": os.path.join(BASE_DIR, "رسائل_غير_مفهومة.txt"),
    "profanity": os.path.join(BASE_DIR, "سباب.txt"),
    "warnings": os.path.join(BASE_DIR, "warnings.json"),
    "seen": os.path.join(BASE_DIR, "seen_members.json"),
    "banned": os.path.join(BASE_DIR, "محظورون.json"),
    "admins": os.path.join(BASE_DIR, "مشرفين.json"),
    "groups": os.path.join(BASE_DIR, "قروبات.json"),
    "bots": os.path.join(BASE_DIR, "bots.json"),
}

for k, p in paths.items():
    if not os.path.isfile(p):
        if p.endswith("warnings.json") or p.endswith("seen_members.json") or p.endswith("banned.json") or p.endswith("admins.json"):
            init = {} 
        elif p.endswith(".json"):
            init = ["http://aminoapps.com/p/tqfa4v3"] if os.path.basename(p) == "قروبات.json" else []
            
        if p.endswith(".json"):
            with open(p, "w", encoding="utf-8") as f:
                json.dump(init, f, ensure_ascii=False, indent=2)
        else:
            open(p, "w", encoding="utf-8").close()

def load_json(p):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        if os.path.basename(p) in ("warnings.json", "seen_members.json", "banned.json", "admins.json"):
            return {}
        return []

def save_json(p, d):
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, ensure_ascii=False, indent=2, fp=f)
    except Exception as e:
        print("Save error", p, e)

warnings_db = load_json(paths["warnings"])
seen_members_db = load_json(paths["seen"])
local_banned = load_json(paths["banned"])
admins_db = load_json(paths["admins"])
monitored_groups = load_json(paths["groups"]) or []
bots_db = load_json(paths["bots"])

qa_responses = {}
try:
    with open(paths["responses"], "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or "||" not in s:
                continue
            q, a = s.split("||", 1)
            q = q.strip()
            answers = [x.strip() for x in a.split(";;") if x.strip()] or [a.strip()]
            if q not in qa_responses:
                qa_responses[q] = []
            for ans in answers:
                if ans not in qa_responses[q]:
                    qa_responses[q].append(ans)
except Exception as e:
    print("خطأ بقراءة ردود.txt:", e)

profanity_list = []
try:
    with open(paths["profanity"], "r", encoding="utf-8") as f:
        for line in f:
            w = line.strip()
            if w:
                profanity_list.append(w)
except Exception as e:
    print("خطأ بقراءة سباب.txt:", e)

TRUE_FALSE_QUESTIONS = [
    ("يوجد أكثر من 8 كواكب في مجموعتنا الشمسية.", "خطأ"),
    ("الحوت الأزرق هو أكبر حيوان على وجه الأرض.", "صح"),
    ("نهر النيل هو أطول نهر في العالم.", "صح"),
    ("النمل يمكنه حمل أشياء تزن 50 ضعف وزنه.", "صح"),
    ("أولمبياد عام 2024 سيقام في مدينة طوكيو.", "خطأ"),
]

NISBA_TOPICS = [
    "الغرور", "النوم في الأماكن الغريبة", "البكاء في الأفلام", 
    "سرعة نسيان الماضي", "هوس الشهرة", "الإدمان على الكولا", 
    "حبك للمشاكل", "إمكانية أن تصبح مليونيراً", "الخجل",
    "تفاؤلك لهذا اليوم", "قدرتك على تحمل الجوع", "جاذبيتك الخفية"
]

SOAREH_QUESTIONS = [
    "سؤال صريح: ما هو القرار الذي لو عاد بك الزمن لتغيره فوراً؟",
    "سؤال صريح: صف نفسك بكلمة واحدة، واشرح لماذا اخترتها.",
    "سؤال صريح: ما هو الشيء الذي تخاف منه حقاً، ولا تجرؤ على البوح به؟",
    "سؤال صريح: متى كانت آخر مرة بكيت فيها، وما هو السبب؟",
    "سؤال صريح: ما هي العادة السيئة التي تحاول التخلص منها ولا تستطيع؟"
]

EATERAF_LINES = [
    "اعترف: أغبى شيء سويته اليوم هو...",
    "اعترف: آخر مرة سحبت على الدوام أو المدرسة كانت بسبب...",
    "اعترف: أحياناً أتصنع أنني أفهم الموضوع عشان ما أبين غبي.",
    "اعترف: أكره لما أحد يسوي لي...",
    "اعترف: ما أقدر أعيش بدون...",
]

CHALLENGE_DARES = [
    "تحدي: أرسل بصمة صوت تقول فيها 'أنا أمزح وأحب الأمزحة' خمس مرات متتالية بأسرع وقت.",
    "تحدي: غير اسمك في القروب إلى 'أفضل لاعب في العالم' لمدة 5 دقائق.",
    "تحدي: أرسل ملصق مضحك جداً من اختيارك في الشات الآن.",
    "تحدي: قم بوصف لون المايك بشكل شعري ومبالغ فيه."
]

def handle_game_command(subclint, content, userId, chatId, msgId, BOT_NAME="رايس"):
    
    
    if content == "العاب":
        
        fio = f"""[BC] 🤖 BOT Raise - رايس 🤖
[C]-----------------------
[C] 🏆 اكتب [ من الفائز 1,2,... ] لاختيار فائز عشوائي من بين الأرقام.
[C]-----------------------
[C] ❓ اكتب [ سؤال صريح ] لأسئلة الصراحة العميقة.
[C]-----------------------
[C] 🗣️ اكتب [ اعترف ] للحصول على طلب اعتراف مضحك.
[C]-----------------------
[C] 🔥 اكتب [ تحدي أو حقيقة ] لاختيار تحدي عشوائي.
[C]-----------------------
[C] ✨ اكتب [ نسبة ] لمعرفة ما تحب ومميزاتك اليوم
[C]-----------------------
[C] ✅ اكتب [ صح او خطأ ] لبدء مسابقة التخمين السريع
[C]-----------------------
[C] 🎤 اكتب [ تحدي مميز ] لبدء لعبة الصوت 🔥
[C]-----------------------
[C] ⚡ اكتب [ تحدي ] لبدء لعبة الكتابة السريعة (أرقام وحروف) ⚡
[C]-----------------------
[C] 🍀 اكتب [ حظ ] لمعرفة حظك اليوم 🎯
[C]-----------------------
[C] 🎰 اكتب [ تنزيل ] لتجربة لعبة الروليت 🎡
[C]-----------------------
[C] 🕹️ اكتب [ ابدا ] لبدء لعبة التنزيل
[C]-----------------------
[C] 🧠 اكتب [ خمن عمري ] لتجربة التخمين المضحك
[C]-----------------------
[C] 🎲 اكتب [ كت تويت ] لأسئلة تفاعلية أعمق
[C]-----------------------
[C] 🔊 اكتب [ قول <نص> ] لتحويل نص لصوت وإرساله
[C]-----------------------
[C] ⚔️ اكتب [ roll <عنصر1> <عنصر2> ... ] لاختيار عشوائي من العناصر (حد أقصى 10)
[C]-----------------------
[C] 🎭 اكتب [ لو خيروك ] للحصول على سؤال تحدي 
[C]-----------------------
[C] 💍 اكتب [ محيبس ] لمعرفة شرح اللعبة
[C]-----------------------
[C] 🦴 اكتب [ جيبة ] لنتيجة عشوائية مضحكة
[C]-----------------------
"""
        try:
            subclint.send_message(chatId=chatId, message=fio)
            return True
        except Exception:
            return False

    
    if content.startswith("من الفائز"):
        
        text_after_command = content.replace("من الفائز", "", 1).strip()
        
        
        numbers_str = re.findall(r'\d+', text_after_command)
        
        
        try:
            numbers = [int(n) for n in numbers_str if 1 <= int(n) <= 10]
        except ValueError:
            numbers = []

        
        if not numbers or len(numbers) < 2 or len(numbers) > 10:
            kki = "[CB] ❌ خطأ في الإدخال!\n[C] يرجى كتابة 'من الفائز' متبوعة برقمين إلى عشرة أرقام مفصولة بفاصلة أو مسافة، والأرقام من 1 إلى 10 فقط (مثال: من الفائز 1, 2, 3, 4, 5)."
            try:
                subclint.send_message(chatId=chatId, message=kki, replyTo=msgId)
            except Exception:
                pass
            return True
            
        
        unique_numbers = list(set(numbers))
        
        
        winner = choice(unique_numbers)
        
        
        numbers_display = ", ".join(map(str, unique_numbers))
        kki = f"[BC] 🏆 لعبة من الفائز (بين الأرقام: {numbers_display}):\n[C] الفائز العشوائي هو: {winner} 🎉"
        
        try:
            subclint.send_message(chatId=chatId, message=kki, replyTo=msgId)
            return True
        except Exception:
            pass
            
    
    if content == "سؤال صريح":
        q = choice(SOAREH_QUESTIONS)
        try:
            subclint.send_message(chatId=chatId, message=f"[BC] ❓ سؤال صريح:\n[C] {q}")
            return True
        except Exception:
            pass

    
    if content == "اعترف":
        e = choice(EATERAF_LINES)
        try:
            subclint.send_message(chatId=chatId, message=f"[BC] 🗣️ اعترف:\n[C] {e}")
            return True
        except Exception:
            pass
            
    
    if content == "تحدي أو حقيقة":
        q_or_d = choice(["حقيقة", "تحدي"])
        
        if q_or_d == "حقيقة":
            q = choice(SOAREH_QUESTIONS)
            msg = f"[BC] 💡 حقيقة:\n[C] {q}"
        else:
            d = choice(CHALLENGE_DARES)
            msg = f"[BC] ⚡ تحدي:\n[C] {d}"
            
        try:
            subclint.send_message(chatId=chatId, message=msg)
            return True
        except Exception:
            pass
            
            
    if content.startswith("roll"):
        
        items_to_choose_from = content.split()[1:11] 
        
        if len(items_to_choose_from) < 2:
            kki = "[CB] ❌ خطأ في الإدخال!\n[C] يرجى كتابة 'roll' متبوعة بعنصرين إلى عشرة عناصر على الأقل، مفصولة بمسافات (مثال: roll عنصر1 عنصر2 عنصر3)."
            try:
                subclint.send_message(chatId=chatId, message=kki, replyTo=msgId)
            except Exception:
                pass
            return True
            
        winner = choice(items_to_choose_from)
        
        items_display = "، ".join(items_to_choose_from)
        kki = f"[BC] 🎲 لعبة الاختيار العشوائي (بين: {items_display}):\n[C] الفائز العشوائي هو: {winner} 🎉"
        
        try:
            subclint.send_message(chatId=chatId, message=kki, replyTo=msgId)
            return True
        except Exception:
            pass

    
    if content == "نسبة":
        topic = choice(NISBA_TOPICS)
        score = randint(1, 10)
        
        if score <= 3:
            comment = "🤦‍♂️ تحتاج إلى تطوير هذا الجانب قليلاً!"
        elif score <= 7:
            comment = "👍 نسبة معقولة، حافظ على مستواك."
        else:
            comment = "🤩 مذهل! أنت ملك/ملكة هذا الشيء!"
            
        kki = f"[BC] ✨ حاسبة {BOT_NAME} للنسب:\n[C] نسبة {topic} لديك هي: {score} من 10\n[C] {comment}"
        try:
            subclint.send_message(chatId=chatId, message=kki, replyTo=msgId)
            return True
        except Exception:
            pass
    
    
    if content == "صح او خطأ":
        question, answer = choice(TRUE_FALSE_QUESTIONS)
        
        def send_question(subclint, chatId, question, answer):
            try:
                subclint.send_message(chatId=chatId, message="[BC] ⏳ مسابقة صح أو خطأ! لديك 10 ثواني للرد...")
                time.sleep(1)
                subclint.send_message(chatId=chatId, message=f"[CB] السؤال:\n{question}")
                time.sleep(10)
                subclint.send_message(chatId=chatId, message=f"[CB] 🔔 انتهى الوقت!\n[C] الإجابة الصحيحة هي: {answer}")
            except Exception:
                pass
        
        T(target=send_question, args=(subclint, chatId, question, answer)).start()
        return True

    
    if content == "تحدي":
        gt = """[BC] ⚡ تحدي الكتابة السريعة (أرقام وحروف)!
[C] أول واحد يكتبها بسرعة وبدقة هو الفائز.
[C] سأرسل الرمز بعد العدّ التنازلي..."""
        try:
            subclint.send_message(chatId=chatId, message=gt)
            time.sleep(1)
            for i in range(3, 0, -1):
                subclint.send_message(chatId=chatId, message=str(i))
                time.sleep(1)
            
            
            chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
            Finish = "".join(sample(chars, 10))
            
            subclint.send_message(chatId=chatId, message=f"[CB] [[ {Finish} ]]")
            return True
        except Exception:
            pass

    
    if content == "تحدي مميز":
        def run_audio_challenge(subclint, chatId):
            try:
                
                random_number = randint(100000, 999999) 
                Finish_text = str(random_number)
                
                subclint.send_message(chatId=chatId, message="[BC] 🎙️ تحدي الأرقام الصوتية:\n[C] سوف أرسل بصمة صوت وأقول فيها الرقم — أول واحد يكتبه بشكل صحيح هو الفائز.")
                time.sleep(3)
                
                lan = "ar"
                name = f"ss_{int(time.time())}.mp3"
                
                tts_text = num2words(random_number, lang='ar')
                
                gTTS(text=tts_text, lang=lan, slow=False).save(name)
                
                max_retries = 5
                
                for attempt in range(max_retries):
                    try:
                        with open(name, "rb") as fff:
                            subclint.send_message(chatId=chatId, file=fff, fileType="audio")
                        
                        break 
                    except Exception as e:
                        if attempt < max_retries - 1:
                            time.sleep(1) 
                        else:
                            raise e 
                
                os.remove(name)
                
                
                subclint.send_message(chatId=chatId, message="[BC] ⏳ انتهى التحدي: 10 ثواني وسأرسل الرقم الصحيح...")
                time.sleep(10)
                subclint.send_message(chatId=chatId, message=f"[CB] 🔔 الإجابة الصحيحة هي:\n{Finish_text}")
                
            except Exception as e:
                try:
                    subclint.send_message(chatId=chatId, message=f"❌ حدث خطأ في تحدي مميز: {e}")
                except Exception:
                    pass
        
        T(target=run_audio_challenge, args=(subclint, chatId)).start()
        return True

    
    if content.startswith("قول"):
        texxxt = content.replace('قول', '', 1).strip()
        if texxxt:
            def run_tts(subclint, chatId, msgId, text):
                try:
                    
                    text_clean = re.sub(r'\[[A-Z]+\]', '', text).strip()
                    if not text_clean:
                        raise ValueError("النص فارغ بعد التنظيف.")
                        
                    lan = "ar"
                    name = os.path.join(BASE_DIR, f"tts_{int(time.time())}.mp3")
                    
                    gTTS(text=text_clean, lang=lan, slow=False).save(name)
                    
                    max_retries = 5 
                    
                    for attempt in range(max_retries):
                        try:
                            with open(name, "rb") as fff:
                                subclint.send_message(chatId=chatId, file=fff, fileType="audio", replyTo=msgId)
                            
                            break 
                        except Exception as e:
                            if attempt < max_retries - 1:
                                time.sleep(1) 
                            else:
                                raise e 
                    
                    os.remove(name)
                except Exception as e:
                    print(f"TTS Error: {e}")
                    
            
            T(target=run_tts, args=(subclint, chatId, msgId, texxxt)).start()
            return True

    
    if content == "لو خيروك":
        g = choice([
            "لو خيروك أن تستبدل اسمك الحالي باسم 'مستر بيضة' مدى الحياة، أو أن تأكل بيضة نيئة في بث مباشر.",
            "لو خيروك أن تلبس جميع ملابسك بالمقلوب لمدة أسبوع، أو أن تستخدم اسم مستعار غبي في كل منصاتك.",
            "لو خيروك أن تكتشف مستقبلك البائس، أو أن تعيش طفولتك البائسة مجدداً.",
            "لو خيروك أن تخسر حاسة التذوق مدى الحياة، أو أن تستمع لأغنية واحدة فقط مدى الحياة."
        ])
        try:
            subclint.send_message(chatId=chatId, message=f"[BC] 🎭 لو خيّروك:\n[C] {g}")
            return True
        except Exception:
            pass

    
    if content == 'كت تويت':
        m = choice([
            "كت تويت| ما هو أغرب حلم تكرر معك؟",
            "كت تويت| ثلاثة أشياء لا تغادر محفظتك أبداً؟",
            "كت تويت| أفضل هدية تلقيتها في حياتك؟",
            "كت تويت| قرار تندم على اتخاذه حتى اليوم؟",
            "كت تويت| ما هو الشيء الذي يجعلك تخسر أعصابك فوراً؟"
        ])
        try:
            subclint.send_message(chatId=chatId, message=f"[BC] 🗣️ كت تويت:\n[C] {m}")
            return True
        except Exception:
            pass

    
    if content == "حظ":
        g = choice([str(i) for i in range(1,11)])
        uiu = f"""[BC] 🍀 حظ اليوم:\n[C] من بين 1 الي 10\n[C] حصلت على -[ {g} ]-"""
        try:
            subclint.send_message(chatId=chatId, message=uiu)
            return True
        except Exception:
            pass

    
    if content == "تنزيل":
        yi = """[BC] 🎰 لعبة التنزيل (الروليت):\n[C] سيتم اختيار رقم عشوائي من 1 إلى 12.\n[C] العضو المختار يهبط من المايك (على مسؤولية المضيف).\n[C] المضيف يكتب 'ابدا' ليبدأ اللعب."""
        try:
            subclint.send_message(chatId=chatId, message=yi)
            return True
        except Exception:
            pass

    
    if content == "ابدا":
        g = choice([str(i) for i in range(1,13)])
        uiu = f"""[BC] 🎯 النتيجة:\n[C] تم اختيار عضو رقم : {g}\n[C] المضيف يكتب 'ابدا' مرة أخرى لاستمرار اللعب."""
        try:
            subclint.send_message(chatId=chatId, message=uiu)
            return True
        except Exception:
            pass

    
    if content.startswith("خمن عمري"):
        io = ['15','16','17','18','19','20','21','22','23','24','25','26','27','28','29','30','75','100','150','250','أنت طاقة نقية، العمر مجرد رقم!']
        g = choice(io)
        try:
            subclint.send_message(chatId=chatId, message=f"[BC] 🧠 تخمين {BOT_NAME}:\n[C] {g}", replyTo=msgId)
            return True
        except Exception:
            pass
            
    
    if content.startswith("احبك"):
        io = ["حبتك حية 🐍", "اعشقك 🥰", "أموت فيك ❤️", "عنجد؟ طيب أثبت لي!", "يا ليتني أعرف من أنت لأحبك أيضاً 😉"]
        g = choice(io)
        try:
            subclint.send_message(chatId=chatId, message=g, replyTo=msgId)
            return True
        except Exception:
            pass

    
    if content == "محيبس":
        
        yi = """[BC] 💍 شرح لعبة محيبس (جيس المحابس):\n[C] 1. يُقسم اللاعبون إلى فريقين.\n[C] 2. يخفي لاعب واحد من الفريق الأول قطعة صغيرة (المحبس) في إحدى يديه، ويخبئها بين بقية اللاعبين في فريقه.\n[C] 3. يرسل الفريق الأول لاعباً واحداً (الجايس) ليحاول تخمين اليد التي فيها المحبس من بين الفريق المنافس.\n[C] 4. الفريق الثاني يطرح أسئلة أو يطلب إظهار بعض الأيدي حتى يتمكن الجايس من التخمين الصحيح.\n[C] 5. في الشات: يمكن لعبها عبر إخفاء شخص ما عن طريق وضع رقم عشوائي يمثل هذا الشخص ومحاولة الجايس تخمين الرقم الصحيح."""
        try:
            subclint.send_message(chatId=chatId, message=yi)
            return True
        except Exception:
            pass

    
    if content == "جيبة":
        g = choice(['عضمة رقم واحد', 'عضمة رقم ثنين', 'عضمة رقم ثلاثة', 'عضمة رقم أربعة', 'عضمة رقم خمسة', 'عضمة رقم ستة', 'عضمة رقم سبعة', 'عضمة رقم ثمانية', 'عضمة رقم تسعة', 'عضمة رقم عشرة'])
        uiu = f"""[BC] 🦴 نتيجة الجيبة:\n[C] تلعب خوش تلعب: {g}"""
        try:
            subclint.send_message(chatId=chatId, message=uiu)
            return True
        except Exception:
            pass

    
    return False

proxies = None
if PROXY_URL:
    proxies = {
        "http": PROXY_URL,
        "https": PROXY_URL,
    }
    print(f"✅ سيتم استخدام بروكسي: {PROXY_URL}")
else:
    print("❌ لم يتم تحديد PROXY_URL، سيتم العمل بدون بروكسي.")

client = amino.Client(api_key=API_KEY, proxies=proxies)

def try_login(retries=6, delay=600):
    for i in range(retries):
        try:
            client.login(email=EMAIL, password=PASSWORD)
            print("تم الدخول إلى Amino.")
            return True
        except Exception as e:
            print("Login attempt failed:", e)
            time.sleep(delay)
    return False

try_login()

last_message = {}
last_response_position = {}

def difflib_ratio(a, b):
    a_norm = a.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه").lower()
    b_norm = b.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه").lower()
    
    a_norm = re.sub(r'[\u064b-\u065e]', '', a_norm)
    b_norm = re.sub(r'[\u064b-\u065e]', '', b_norm)
    a_norm = re.sub(r'(.)\1+', r'\1', a_norm)
    b_norm = re.sub(r'(.)\1+', r'\1', b_norm)

    try:
        return difflib.SequenceMatcher(None, a_norm.strip(), b_norm.strip()).ratio()
    except Exception:
        return 0.0

def add_local_ban(uid, duration_seconds=None):
    global local_banned
    if uid == DEV_UID: return
    expiry = None if duration_seconds is None else int(time.time()) + int(duration_seconds)
    if not isinstance(local_banned, dict):
        local_banned = {}
    local_banned[uid] = expiry
    save_json(paths["banned"], local_banned)

def remove_local_ban(uid):
    global local_banned
    if uid == DEV_UID: return
    
    if not isinstance(local_banned, dict):
        local_banned = load_json(paths["banned"])
        if not isinstance(local_banned, dict):
            local_banned = {}

    if uid in local_banned:
        local_banned.pop(uid, None)
        save_json(paths["banned"], local_banned)
        return True
    return False
    

def is_local_banned(uid):
    if not uid:
        return False
    if uid not in local_banned:
        return False
    exp = local_banned.get(uid)
    if exp is None:
        return True
    if exp is not None and exp > int(time.time()):
        return True
    local_banned.pop(uid, None)
    save_json(paths["banned"], local_banned)
    return False

def safe_send(sub, chatId=None, message="", **kwargs):
    try:
        if chatId:
            sub.send_message(chatId=chatId, message=message, **kwargs)
        else:
            sub.send_message(message=message, **kwargs)
        return True
    except Exception:
        try:
            userId = kwargs.get("userId")
            if userId:
                client.send_message(userId=userId, message=message)
                return True
        except Exception:
            pass
    return False

def delete_message(sub, messageId, chatId=None):
    try:
        if chatId:
            sub.delete_message(chatId=chatId, messageId=messageId)
            return True
        sub.delete_message(messageId=messageId)
        return True
    except Exception:
        try:
            if hasattr(sub, "session") and hasattr(sub, "comId") and chatId:
                url = f"https://service.aminoapps.com/api/v1/x{sub.comId}/s/chat/thread/{chatId}/message/{messageId}"
                r = sub.session.delete(url, headers=sub.parse_headers(), timeout=10)
                return r.status_code in (200, 204)
        except Exception:
            pass
    return False

def pin_message(sub, messageId, chatId=None):
    try:
        sub.pin_message(chatId=chatId, messageId=messageId)
        return True
    except Exception:
        try:
            if hasattr(sub, "session") and hasattr(sub, "comId") and chatId:
                url = f"https://service.aminoapps.com/api/v1/x{sub.comId}/s/chat/thread/{chatId}/pin"
                r = sub.session.post(url, json={"messageId": messageId}, headers=sub.parse_headers(), timeout=10)
                return r.status_code in (200, 204)
        except Exception:
            pass
    return False

def kick_user(sub, uid, chatId=None, temporary=True):
    if uid == DEV_UID:
        return False

    if temporary:
        methods = [
            lambda: sub.kick(chatId=chatId, userId=uid),
            lambda: client.kick(chatId=chatId, userId=uid)
        ]
    else:
        methods = [
            lambda: sub.ban(chatId=chatId, userId=uid),
            lambda: client.ban(chatId=chatId, userId=uid),
            lambda: sub.kick(chatId=chatId, userId=uid)
        ]

    for fn in methods:
        try:
            fn()
            return True
        except Exception:
            pass
            
    if not temporary and hasattr(sub, "session") and hasattr(sub, "comId") and chatId:
        try:
            urls = [
                f"https://service.aminoapps.com/api/v1/x{sub.comId}/s/chat/thread/{chatId}/member/{uid}/ban",
                f"https://service.aminoapps.com/api/v1/x{sub.comId}/s/channel/{chatId}/member/{uid}/ban"
            ]
            for url in urls:
                try:
                    r = sub.session.post(url, json={}, headers=sub.parse_headers(), timeout=10)
                    if r.status_code in (200, 204):
                        return True
                except Exception:
                    pass
        except Exception:
            pass
    return False

def is_supervisor(uid):
    if uid == DEV_UID:
        return True
    if isinstance(admins_db, dict):
        return admins_db.get(uid, False)
    if isinstance(admins_db, list):
        return uid in admins_db
    return False

def get_user_nickname(uid):
    try:
        profile = client.get_user_info(userId=uid)
        return profile.get("nickname", "") if isinstance(profile, dict) else ""
    except Exception:
        return ""

def check_command_protection(author_uid, target_uid, chat_id, mid, sub):
    if target_uid == DEV_UID:
        msg = f"⚠️ لا أستطيع تنفيذ أي أمر ضد المطور، حساب المطور: http://aminoapps.com/p/bnudkj"
        safe_send(sub, chat_id, msg, replyTo=mid)
        return True

    if target_uid == author_uid:
        return False

    if is_supervisor(target_uid):
        if author_uid != DEV_UID and is_supervisor(author_uid):
            msg = "❌ لا يمكن للمشرفين تنفيذ أوامر (طرد، حظر، إزالة إشراف) ضد مشرفين آخرين."
            safe_send(sub, chat_id, msg, replyTo=mid)
            return True
        
    return False

def mention_user_in_message(sub, chatId, uid, text, replyTo=None):
    try:
        mentioned = [{"uid": uid}]
        try:
            sub.send_message(chatId=chatId, message=text, extensions={"mentionedArray": mentioned}, replyTo=replyTo)
            return True
        except Exception:
            pass
        try:
            sub.send_message(chatId=chatId, message=text, mentionUserIds=[uid], replyTo=replyTo)
            return True
        except Exception:
            pass
    except Exception:
        pass
    
    try:
        nickname = get_user_nickname(uid)
        
        if nickname == "":
            safe_send(sub, chatId, text, replyTo=replyTo)
        else:
            safe_send(sub, chatId, f"@{nickname} {text}", replyTo=replyTo)
        return True
    except Exception:
        try:
            safe_send(sub, chatId, text, replyTo=replyTo)
            return True
        except Exception:
            return False

def mention_everyone_in_chat(sub, chatId, replyTo=None, message_text="منشن من رايس"):
    try:
        resp = sub.get_chat_members(chatId=chatId)
        members = resp.get("memberList", []) if isinstance(resp, dict) else (resp or [])
        mentioned = [{"uid": m.get("uid")} for m in members if isinstance(m, dict) and m.get("uid")]
        
        if mentioned:
            try:
                sub.send_message(chatId=chatId, message=message_text, extensions={"mentionedArray": mentioned}, replyTo=replyTo)
                return True
            except Exception:
                pass
        
        safe_send(sub, chatId, "@all " + message_text, replyTo=replyTo)
        return True
    except Exception as e:
        print(f"Error mentioning everyone: {e}")
        return False

def handle_text_mentioning_dev(txt, sub, chat_id, mid):
    try:
        low = txt.lower()
        if not any(k.lower() in low for k in DEV_KEYWORDS):
            return False
        
        mention_user_in_message(sub, chat_id, DEV_UID, f"هذا المطور: {DEV_LINK}", replyTo=mid)
        
        return True
    except Exception:
        return False

def contains_profanity_exact(text):
    if not text:
        return None

    txt_lower = text.lower()
    txt_normalized = re.sub(r'(.)\1+', r'\1', txt_lower)
    padded_normalized = " " + txt_normalized + " "

    for bad in profanity_list:
        if not bad:
            continue
        b = bad.strip().lower()
        if not b:
            continue
            
        b_normalized = re.sub(r'(.)\1+', r'\1', b)

        try:
            if b_normalized in txt_normalized:
                if f" {b_normalized} " in padded_normalized or txt_normalized.strip() == b_normalized:
                    return bad
            
            pattern = re.compile(r'\b' + re.escape(b_normalized) + r'\b', re.IGNORECASE)
            if pattern.search(txt_normalized):
                return bad

        except Exception:
            continue
            
    return None

def search_in_responses(text, chatId=None, threshold=0.5):
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None

    if text in qa_responses:
        best_match = text
        best_ratio = 1.0
    else:
        keys = list(qa_responses.keys())
        if not keys:
            return None
            
        best_match = None
        best_ratio = 0.0
        
        for k in keys:
            ratio = difflib_ratio(k, text)
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = k

        if best_ratio < threshold:
            return None

    answers = qa_responses.get(best_match, [])
    if not answers:
        return None
        
    last_key = (chatId, best_match)
    last_response = last_response_position.get(last_key)
    
    choices = [a for a in answers if a != last_response] or answers
    choice = random.choice(choices)
    
    last_response_position[last_key] = choice
    
    return choice

def get_default_response(chatId=None):
    defaults_ar = [
"خير شتبي؟",
        "نعم؟....",
        "شتبي؟",
        "لاحول مزعج انت",
        "تصدق! مليت منك وربي",
        "يكفي مليت ما برد",
        "أفا، رجعت لي؟",
        "زين؟ وبعدين؟",
        "مو فاضي لك",
        "اخلص، عندي شغل",
        "ترا ما نمت، وش بغيت؟",
        "يا رب وش هالنِشبة؟",
        "ما فهمت وش تقول، تعبتني",
        "يا ليت تتكلم بوضوح، مو ناقص تعقيد",
        "وش هاللغة اللي تتكلم فيها؟",
        "بصراحة، السؤال هذا مو لي، أسأل غيري",
        "وش المطلوب بالضبط؟ لا تلف وتدور",
        "ماني فاهم قصدك.. عيد صياغة السؤال بسرعة",
        "أنا بوت، مو ساحر عشان أفهم وش بخاطرك"
    ]
    defaults_qa = qa_responses.get("افتراضي", []) + qa_responses.get("default", [])
    defaults = defaults_qa or defaults_ar
        
    last_key = (chatId, "افتراضي")
    last_response = last_response_position.get(last_key)
    
    choices = [a for a in defaults if a != last_response] or defaults
    choice = random.choice(choices)
    
    last_response_position[last_key] = choice
    return choice

def fetch_messages(sub, chatId, size=1):
    try:
        url = f"https://service.aminoapps.com/api/v1/x{sub.comId}/s/chat/thread/{chatId}/message?v=2&pagingType=t&size={size}"
        r = sub.session.get(url, headers=sub.parse_headers(), timeout=15)
        if r.status_code == 200:
            return r.json().get("messageList", [])
    except Exception:
        pass
    return []

def get_chat_and_community_ids(link):
    try:
        obj = client.get_from_code(link)
        
        comId = getattr(obj, 'comId', None)
        objectId = getattr(obj, 'objectId', None)
        
        if comId and objectId:
            return comId, objectId, link
            
    except Exception as e:
        print(f"فشل جلب الأكواد من الرابط ({link}): {e}")

    return None, None, None

def add_group_link(link, join_if_needed=True):
    try:
        comId, objectId, full_link = get_chat_and_community_ids(link)
        if not comId or not objectId or not full_link:
            return False
            
        if full_link in monitored_groups:
            return False
            
        if join_if_needed:
            try:
                client.join_community(comId)
            except Exception:
                pass
            
            try:
                subtmp = amino.SubClient(comId=comId, profile=client.profile)
                subtmp.join_chat(chatId=objectId)
            except Exception:
                pass
        
        monitored_groups.append(full_link)
        save_json(paths["groups"], monitored_groups)
        
        return True
    except Exception:
        return False

def remove_group_link(link, leave_if_needed=True):
    try:
        comId, objectId, full_link = get_chat_and_community_ids(link)
        
        if full_link in monitored_groups:
            
            if leave_if_needed and comId and objectId:
                try:
                    subtmp = amino.SubClient(comId=comId, profile=client.profile)
                    subtmp.leave_chat(chatId=objectId)
                except Exception:
                    pass
            
            monitored_groups.remove(full_link)
            save_json(paths["groups"], monitored_groups)
            
            return True
    except Exception:
        pass
    return False

def get_supervisors_list():
    try:
        out = []
        if isinstance(admins_db, dict):
            uids = [k for k, v in admins_db.items() if v]
        elif isinstance(admins_db, list):
            uids = list(admins_db)
        else:
            uids = []
            
        for uid in uids:
            try:
                info = client.get_user_info(userId=uid)
                if isinstance(info, dict):
                    out.append(info.get("nickname", uid))
                else:
                    out.append(str(uid))
            except Exception:
                out.append(str(uid))
        return out
    except Exception:
        return []

def process_message(m, sub, chat_obj):
    try:
        mid = m.get("messageId")
        author = m.get("author") or {}
        if isinstance(author, dict):
            author_uid = author.get("uid")
        else:
            author_uid = getattr(author, "uid", None)

        txt = m.get("content", "") or ""
        if not isinstance(txt, str):
            txt = str(txt)
            
        chat_id = chat_obj["objectId"]

        my_uid = getattr(getattr(client, "profile", {}), "userId", None)
        
        if author_uid == my_uid:
            return

        group_warnings = warnings_db.get(chat_id, {})
        is_group_banned_status = (
            author_uid in group_warnings and 
            group_warnings[author_uid].get("status") == "group_banned"
        )

        if is_group_banned_status:
            final_kick_msg = "تم الحظر الدائم من القروب" 
            
            kick_permanent_success = kick_user(sub, author_uid, chatId=chat_id, temporary=False)
            
            if kick_permanent_success:
                mention_user_in_message(sub, chat_id, author_uid, final_kick_msg, replyTo=mid)
            else:
                kick_user(sub, author_uid, chatId=chat_id, temporary=True)
                mention_user_in_message(sub, chat_id, author_uid, final_kick_msg + " (طرد احتياطي).", replyTo=mid)
                
            return

        if is_local_banned(author_uid):
            return

        if last_message.get(chat_id) == mid:
            return
        last_message[chat_id] = mid

        exts = m.get("extensions", {}) or {}
        mentioned = False
        mentionedArray = exts.get("mentionedArray", []) if isinstance(exts.get("mentionedArray", []), list) else []
        for u in mentionedArray:
            if isinstance(u, dict) and u.get("uid") == my_uid:
                mentioned = True
                break

        reply_to = exts.get("replyMessage", {})
        reply_to_me = False
        if isinstance(reply_to, dict):
            rep_auth = reply_to.get("author") or {}
            if isinstance(rep_auth, dict):
                rep_uid = rep_auth.get("uid")
            else:
                rep_uid = getattr(rep_auth, "uid", None)
            reply_to_me = (rep_uid == my_uid)

        found_bad = contains_profanity_exact(txt)

        if author_uid == DEV_UID and found_bad:
            try:
                delete_message(sub, mid, chatId=chat_id)
                safe_send(sub, chat_id, "⚠️ عيب تسب وانت المطور، تصرف بشكل لائق!", replyTo=mid)
            except Exception:
                pass
            return
            
        if found_bad:
            try:
                delete_message(sub, mid, chatId=chat_id)
            except Exception:
                pass
            
            if chat_id not in warnings_db:
                warnings_db[chat_id] = {}
            if author_uid not in warnings_db[chat_id]:
                warnings_db[chat_id][author_uid] = {"count": 0, "last_bad": "", "status": None}
                
            user_warns = warnings_db[chat_id][author_uid]
            
            user_warns["count"] = user_warns.get("count", 0) + 1
            user_warns["last_bad"] = found_bad
                
            warnings_db[chat_id][author_uid] = user_warns
            save_json(paths["warnings"], warnings_db)
            
            if user_warns["count"] >= 4:
                final_kick_msg = "ابلع طرد، انذرتك ثلاث مرات ولا سمعت. أنت محظور من العودة للقروب."
                
                success = kick_user(sub, author_uid, chatId=chat_id, temporary=False)
                
                warnings_db[chat_id][author_uid]["status"] = "group_banned"
                save_json(paths["warnings"], warnings_db)
                
                if success:
                    mention_user_in_message(sub, chat_id, author_uid, final_kick_msg, replyTo=mid)
                else:
                    kick_user(sub, author_uid, chatId=chat_id, temporary=True) 
                    mention_user_in_message(sub, chat_id, author_uid, f"فشل الحظر الدائم! تم الطرد وتعيين حظر قروب دائم. {final_kick_msg}", replyTo=mid)
            
            elif user_warns["count"] >= 1 and user_warns["count"] <= 3:
                warn_count = user_warns['count']
                if warn_count == 1:
                    warning_msg = f"ابلع إنذار أول، لا تسب بالقروب وتجيب العيد! (الإنذار 1/3)"
                elif warn_count == 2:
                    warning_msg = f"ابلع إنذار ثاني، قلت لك لا تسب! أحترم نفسك. (الإنذار 2/3)"
                elif warn_count == 3:
                    warning_msg = f"إنذار أخير (3/3)، المخالفة القادمة طرد نهائي من القروب!"
                else:
                    warning_msg = f"تحذير {warn_count}/3: راقب لغتك!"
                    
                mention_user_in_message(sub, chat_id, author_uid, warning_msg, replyTo=mid)

            return

        poli_words = ["سياسة", "انتخابات", "رئيس", "حكومة", "حزبي", "حزب", "انتخاب", "برلمان", "قانون الانتخاب", "سياسي"]
        if any(w in txt.lower() for w in poli_words):
            try:
                safe_send(sub, chat_id, "تحذير: السياسة ممنوع سالفتها هنا. جب سيرة غيرها لا تبلع  .", replyTo=mid)
            except:
                pass
            try:
                if author_uid:
                    client.send_message(userId=author_uid, message="تم تحذيرك: الحديث عن السياسة ممنوع.")
            except:
                pass
            return

        if handle_text_mentioning_dev(txt, sub, chat_id, mid):
            return
            
        if handle_game_command(sub, txt.strip().lower(), author_uid, chat_id, mid, BOT_NAME_AR):
            return


        author_is_supervisor = is_supervisor(author_uid)

        if (author_uid == DEV_UID) or author_is_supervisor:
            
            
            if isinstance(txt, str) and txt.startswith(("!معلومات", "معلومات العضو")):
                mentioned_list = exts.get("mentionedArray", [])
                user_link_match = re.search(r'(http://aminoapps\.com/p/[a-zA-Z0-9]+)', txt)
                
                target_uid = None
                
                if mentioned_list:
                    target_uid = mentioned_list[0].get("uid")
                elif user_link_match:
                    link = user_link_match.group(0)
                    try:
                        obj = client.get_from_code(link)
                        target_uid = getattr(obj, "objectId", None)
                    except:
                        pass
                
                if not target_uid:
                    safe_send(sub, chat_id, "❌ لتنفيذ الأمر، يجب عمل منشن (Tag) للعضو أو إرسال رابط بروفايله.", replyTo=mid)
                    return
                
                try:
                    profile = client.get_user_info(userId=target_uid)
                    info = profile.get('userProfile', {})
                    
                    nickname = info.get("nickname", "N/A")
                    level = info.get("level", 0)
                    reputation = info.get("reputation", 0)
                    
                    created_time_str = info.get("createdTime")
                    join_date = "N/A"
                    if created_time_str:
                         try:
                            join_date = created_time_str.split('T')[0] 
                         except:
                            join_date = created_time_str 

                    message = f"""[BC]👤 معلومات العضو ({nickname}):
[C]-----------------------
[C] معرف العضو (UID): {target_uid}
[C] المستوى (Level): {level}
[C] السمعة (Reputation): {reputation}
[C] تاريخ الانضمام: {join_date}
[C] رابط البروفايل: http://aminoapps.com/p/{target_uid}
[C]-----------------------"""
                    safe_send(sub, chat_id, message, replyTo=mid)
                except Exception as e:
                    safe_send(sub, chat_id, f"❌ فشل جلب معلومات العضو. (الخطأ: {e})", replyTo=mid)

                return
            
            if isinstance(txt, str) and txt.startswith(("عفو عن", "العفو عن")):
                
                mentioned_list = exts.get("mentionedArray", [])
                user_link_match = re.search(r'(http://aminoapps\.com/p/[a-zA-Z0-9]+)', txt)
                
                target_uid = None
                
                if mentioned_list:
                    target_uid = mentioned_list[0].get("uid")
                elif user_link_match:
                    link = user_link_match.group(0)
                    try:
                        obj = client.get_from_code(link)
                        target_uid = getattr(obj, "objectId", None)
                    except:
                        pass
                
                if not target_uid:
                    safe_send(sub, chat_id, "❌ لم أجد العضو المطلوب للعفو. تأكد من عمل منشن أو إرسال رابط العضو.", replyTo=mid)
                    return
                
                if check_command_protection(author_uid, target_uid, chat_id, mid, sub): return

                if chat_id in warnings_db and target_uid in warnings_db[chat_id]:
                    warnings_db[chat_id][target_uid].pop("status", None)
                    warnings_db[chat_id][target_uid]["count"] = 0 
                    warnings_db[chat_id][target_uid].pop("last_bad", None)
                    save_json(paths["warnings"], warnings_db)
                    
                    try:
                        if hasattr(sub, "unban"):
                            sub.unban(chatId=chat_id, userId=target_uid)
                    except:
                        pass
                        
                    mention_user_in_message(sub, chat_id, target_uid, "تم العفو عنه يقدر يدخل القروب الأن..", replyTo=mid)
                    
                else:
                    safe_send(sub, chat_id, "❌ العضو ليس محظوراً على مستوى هذا القروب.", replyTo=mid)
                return

            
            if isinstance(txt, str) and txt.startswith(("حظر قروب", "حظر_قروب")):
                mentioned_list = exts.get("mentionedArray", [])
                user_link_match = re.search(r'(http://aminoapps\.com/p/[a-zA-Z0-9]+)', txt)
                
                target_uid = None
                
                if mentioned_list:
                    target_uid = mentioned_list[0].get("uid")
                elif user_link_match:
                    link = user_link_match.group(0)
                    try:
                        obj = client.get_from_code(link)
                        target_uid = getattr(obj, "objectId", None)
                    except:
                        pass
                
                if not target_uid:
                    safe_send(sub, chat_id, "❌ لم أجد العضو المطلوب للحظر. تأكد من عمل منشن أو إرسال رابط العضو.", replyTo=mid)
                    return
                
                if check_command_protection(author_uid, target_uid, chat_id, mid, sub): return

                final_kick_msg = "تم الحظر الدائم من القروب" 
                
                ok = kick_user(sub, target_uid, chatId=chat_id, temporary=False) 
                
                if chat_id not in warnings_db: warnings_db[chat_id] = {}
                if target_uid not in warnings_db[chat_id]: warnings_db[chat_id][target_uid] = {"count": 0, "last_bad": "", "status": None}
                warnings_db[chat_id][target_uid]["status"] = "group_banned"
                save_json(paths["warnings"], warnings_db)
                
                if ok:
                    mention_user_in_message(sub, chat_id, target_uid, final_kick_msg, replyTo=mid)
                else:
                    kick_user(sub, target_uid, chatId=chat_id, temporary=True)
                    mention_user_in_message(sub, chat_id, target_uid, f"✅ تم الطرد وحفظ حالة الحظر الدائم في القروب. {final_kick_msg}", replyTo=mid)

                return

            if isinstance(txt, str) and re.match(r"^!?(كتم|حظر محلي)[123]?\b", txt):
                parts = txt.split()
                code = None
                m0 = re.match(r"^!?(كتم|حظر محلي)([123])\b", txt)
                if m0:
                    code = m0.group(2)
                elif len(parts) >= 2 and parts[-1] in ("1", "2", "3"):
                    code = parts[-1]

                mentioned_list = exts.get("mentionedArray", [])
                
                if not mentioned_list:
                    safe_send(sub, chat_id, "❌ منشن المستخدم يا معلم عشان أقدر أشتغل.", replyTo=mid)
                else:
                    if code is None: code = "3"
                    
                    for u in mentioned_list:
                        uid = u.get("uid")
                        if not uid: continue
                        
                        if check_command_protection(author_uid, uid, chat_id, mid, sub): continue

                        if code == "1":
                            add_local_ban(uid, 3600)
                            safe_send(sub, chat_id, "تم الكتم لن أرد عليه لمده ساعة", replyTo=mid)
                        elif code == "2":
                            add_local_ban(uid, 86400)
                            safe_send(sub, chat_id, "تم الكتم لمدة لمدة 24 ساعة", replyTo=mid)
                        elif code == "3":
                            add_local_ban(uid, None)
                            safe_send(sub, chat_id, "تم الكتم لن أرد عليه للأبد", replyTo=mid)
                return

            
            if isinstance(txt, str) and txt.strip() in ("فك الكتم", "فك الحظر", "!فك الكتم", "!فك الحظر") or txt.startswith(("!فك_الكتم", "فك_الحظر", "!فك_الحظر")):
                mentioned_list = exts.get("mentionedArray", [])
                user_link_match = re.search(r'(http://aminoapps\.com/p/[a-zA-Z0-9]+)', txt)

                target_uids = []
                if mentioned_list:
                    target_uids.extend([u.get("uid") for u in mentioned_list if u.get("uid")])
                elif user_link_match:
                    link = user_link_match.group(0)
                    try:
                        obj = client.get_from_code(link)
                        target_uids.append(getattr(obj, "objectId", None))
                    except:
                        pass
                
                if not target_uids:
                    safe_send(sub, chat_id, "❌ يرجى عمل منشن (Tag) للعضو أو إرسال رابطه لفك الكتم عنه.", replyTo=mid)
                    return

                success_count = 0
                for uid in target_uids:
                    if not uid: continue
                    if check_command_protection(author_uid, uid, chat_id, mid, sub): continue

                    if remove_local_ban(uid): 
                        success_count += 1

                if success_count > 0:
                    safe_send(sub, chat_id, f"✅ تم فك **الكتم** عن {success_count} عضو، عطوهم فرصة ثانية.", replyTo=mid)
                else:
                    safe_send(sub, chat_id, "❌ لم يتم العثور على أي من الأعضاء المذكورين في قائمة الكتم المحلي.", replyTo=mid)
                return

            if author_uid == DEV_UID and isinstance(txt, str) and txt.startswith(("ترقيه إشراف", "ترقية إشراف")):
                mentioned_list = exts.get("mentionedArray", [])
                if not mentioned_list:
                    safe_send(sub, chat_id, "❌ منشن المستخدم يا مطوري العزيز.", replyTo=mid)
                else:
                    for u in mentioned_list:
                        uid = u.get("uid")
                        if uid:
                            if isinstance(admins_db, dict):
                                admins_db[uid] = True
                            elif isinstance(admins_db, list) and uid not in admins_db:
                                admins_db.append(uid)
                            save_json(paths["admins"], admins_db)
                            try:
                                sub.promote(userId=uid)
                            except:
                                pass
                            safe_send(sub, chat_id, "✅ مبروك تمت ترقيته إشراف، صار معلم.", replyTo=mid)
                return

            if isinstance(txt, str) and txt.startswith(("ازاله إشراف", "إزالة إشراف")):
                mentioned_list = exts.get("mentionedArray", [])
                if not mentioned_list:
                    safe_send(sub, chat_id, "❌ منشن المستخدم اللي تبي تنزله من الإشراف.", replyTo=mid)
                else:
                    for u in mentioned_list:
                        uid = u.get("uid")
                        if uid:
                            if check_command_protection(author_uid, uid, chat_id, mid, sub): return
                            if isinstance(admins_db, dict):
                                admins_db.pop(uid, None)
                            elif isinstance(admins_db, list) and uid in admins_db:
                                admins_db.remove(uid)
                            save_json(paths["admins"], admins_db)
                            try:
                                sub.demote(userId=uid)
                            except:
                                pass
                            safe_send(sub, chat_id, "✅ تمت إزالة الإشراف، بطلنا منه.", replyTo=mid)
                return

            if isinstance(txt, str) and re.match(r"^طرد[12]?\b", txt):
                parts = txt.split()
                kick_type = None
                m0 = re.match(r"^طرد([12])\b", txt)
                if m0:
                    kick_type = m0.group(1)
                elif len(parts) >= 2 and parts[-1] in ("1", "2"):
                    kick_type = parts[-1]
                
                if kick_type is None:
                    kick_type = "1" 

                mentioned_list = exts.get("mentionedArray", [])
                if not mentioned_list:
                    safe_send(sub, chat_id, "❌ منشن المستخدم اللي تبي تطرده، وش تنتظر؟", replyTo=mid)
                else:
                    for u in mentioned_list:
                        uid = u.get("uid")
                        if not uid: continue
                        
                        if check_command_protection(author_uid, uid, chat_id, mid, sub): return
                        
                        try:
                            if kick_type == "1":
                                ok = kick_user(sub, uid, chatId=chat_id, temporary=True)
                                safe_send(sub, chat_id, "تم الطرد" if ok else "فشل الطرد العادي.", replyTo=mid)
                            
                            elif kick_type == "2":
                                ok = kick_user(sub, uid, chatId=chat_id, temporary=False)
                                
                                if ok:
                                    safe_send(sub, chat_id, "تم الطرد", replyTo=mid)
                                else:
                                    ok2 = kick_user(sub, uid, chatId=chat_id, temporary=True)
                                    
                                    if chat_id not in warnings_db: warnings_db[chat_id] = {}
                                    if uid not in warnings_db[chat_id]: warnings_db[chat_id][uid] = {"count": 0, "last_bad": "", "status": None}
                                    warnings_db[chat_id][uid]["status"] = "group_banned"
                                    save_json(paths["warnings"], warnings_db)
                                    
                                    if ok2:
                                        safe_send(sub, chat_id, "تم الطرد", replyTo=mid)
                                    else:
                                        safe_send(sub, chat_id, "فشل الطرد: تم حفظ حظر قروب دائم.", replyTo=mid)
                        except Exception as e:
                            safe_send(sub, chat_id, f"فشل الطرد: {e}", replyTo=mid)
                return

            if isinstance(txt, str) and txt in ("!عرض", "!عرض_فقط", "إطلاع القروب"):
                done = False
                error_detail = ""
                
                try:
                    sub.update_chat(chatId=chat_id, content="view_only") 
                    done = True
                except Exception as e:
                    error_detail = f"فشل المحاولة 1: {e}"
                    
                if not done:
                    try:
                        sub.set_chat_permission(chatId=chat_id, permission="view_only")
                        done = True
                    except Exception as e:
                        error_detail = f"فشل المحاولة 2: {e}"

                if not done:
                    try:
                        sub.set_permissions(chatId=chat_id, permissions={"sendMessage": False})
                        done = True
                    except Exception as e:
                        error_detail = f"فشل المحاولة 3: {e}"


                if done:
                    safe_send(sub, chat_id, "✅ تم تفعيل وضع العرض فقط. الكل يسكت.", replyTo=mid)
                else:
                    msg = "❌ فشل تفعيل وضع العرض فقط."
                    if author_uid == DEV_UID:
                         msg += f" (تفاصيل: تأكد من صلاحية البوت كـ Host/Co-Host. الخطأ الأخير: {error_detail})"
                    else:
                         msg += " (قد تكون الصلاحيات غير كافية للبوت)."
                         
                    safe_send(sub, chat_id, msg, replyTo=mid)
                return

            if isinstance(txt, str) and txt in ("!فتح_الدردشة", "!فتح"):
                done = False
                try:
                    sub.set_chat_permission(chatId=chat_id, permission="all")
                    done = True
                except:
                    try:
                        sub.update_chat(chatId=chat_id, permission="all")
                        done = True
                    except:
                        try:
                            sub.set_permissions(chatId=chat_id, permissions={"sendMessage": True})
                            done = True
                        except:
                            pass
                safe_send(sub, chat_id, "✅ تم فتح الدردشة. سولفوا يالله." if done else "الميزة غير متاحة.", replyTo=mid)
                return

            if isinstance(txt, str) and txt == "!حذف":
                try:
                    reply_msg = exts.get("replyMessage")
                    target_mid = reply_msg.get("messageId") if isinstance(reply_msg, dict) else None
                    if target_mid and delete_message(sub, target_mid, chatId=chat_id):
                        safe_send(sub, chat_id, "✅ حذفت الرسالة عشانك.", replyTo=mid)
                    else:
                        safe_send(sub, chat_id, "❌ رد على رسالة عشان أحذفها.", replyTo=mid)
                except Exception as e:
                    safe_send(sub, chat_id, f"خطأ بالحذف: {e}", replyTo=mid)
                return

            if isinstance(txt, str) and txt == "!تثبيت":
                try:
                    reply_msg = exts.get("replyMessage")
                    target_mid = reply_msg.get("messageId") if isinstance(reply_msg, dict) else None
                    if target_mid and pin_message(sub, target_mid, chatId=chat_id):
                        safe_send(sub, chat_id, "✅ أبشر تم تثبيت الرسالة.", replyTo=mid)
                    else:
                        safe_send(sub, chat_id, "❌ رد على رسالة عشان أثبتها.", replyTo=mid)
                except Exception as e:
                    safe_send(sub, chat_id, f"خطأ بالتثبيت: {e}", replyTo=mid)
                return

            if isinstance(txt, str) and txt.strip() in ("منشن", "!منشن", "!mention", "منشن_الكل"):
                ok = mention_everyone_in_chat(sub, chat_id, replyTo=mid, message_text="يا جماعة الخير، أحد المشرفين يبغاكم.")
                safe_send(sub, chat_id, "✅ منشنت الكل، يالله اشغلهم." if ok else "فشل منشن.", replyTo=mid)
                return

            if isinstance(txt, str) and txt.strip() in ("قائمة المشرفين", "قائمة_المشرفين", "!مشرفين"):
                supl = get_supervisors_list()
                out = "المعلمين بالقروب هم:\n" + "\n".join(supl) if supl else "ما عندنا مشرفين حالياً."
                safe_send(sub, chat_id, out, replyTo=mid)
                return

            if isinstance(txt, str) and txt.startswith(("اضف قروب", "إضافة قروب", "اضف_ قروب")):
                parts = txt.split()
                link = None
                m_link = re.search(r'(https?://aminoapps\.com/p/[a-zA-Z0-9]+)', txt)
                if m_link:
                    link = m_link.group(0)
                elif ":" in txt:
                    link = txt.split(":", 1)[1].strip()
                elif len(parts) >= 2:
                    link = parts[-1].strip()
                    
                if not link:
                    safe_send(sub, chat_id, "❌ أرسل رابط القروب بعد الأمر يا شنب.", replyTo=mid)
                    return
                    
                if add_group_link(link, join_if_needed=True):
                    safe_send(sub, chat_id, f"✅ تم إضافة القروب والانضمام إليه بنجاح. سأعيد التشغيل الآن.", replyTo=mid)
                    time.sleep(1) 
                    restart_program()
                else:
                    safe_send(sub, chat_id, f"❌ القروب موجود مسبقاً أو صار فيه غلط أثناء الانضمام. تأكد من الرابط.", replyTo=mid)
                return

            if isinstance(txt, str) and txt.startswith(("ازالة قروب", "ازل قروب", "إزالة قروب", "إزالة_قروب")):
                parts = txt.split()
                link = None
                m_link = re.search(r'(https?://aminoapps\.com/p/[a-zA-Z0-9]+)', txt)
                if m_link:
                    link = m_link.group(0)
                elif ":" in txt:
                    link = txt.split(":", 1)[1].strip()
                elif len(parts) >= 2:
                    link = parts[-1].strip()
                    
                if not link:
                    safe_send(sub, chat_id, "❌ أرسل رابط الحذف بعد الأمر يا قلبي.", replyTo=mid)
                    return
                    
                ok = remove_group_link(link)
                if ok:
                    safe_send(sub, chat_id, f"✅ تم إزالة القروب والمغادرة بنجاح. سأعيد التشغيل الآن.", replyTo=mid)
                    time.sleep(1)
                    restart_program()
                else:
                    safe_send(sub, chat_id, f"❌ القروب مو موجود عندي عشان أحذفه أو فشلت المغادرة.", replyTo=mid)
                return

            if isinstance(txt, str) and txt.strip() in ("قائمة القروبات", "قروبات", "قائمة_القروبات"):
                gl = monitored_groups
                safe_send(sub, chat_id, "القروبات اللي أراقبها:\n" + ("\n".join(gl) if gl else "ما أراقب ولا قروب حالياً."), replyTo=mid)
                return

            if isinstance(txt, str) and txt.strip() in ("بوت", "بوت رايس", "قائمة البوت", "menu", "ميو", "!قائمة", "!menu"):
                
                menu = f"""[BC] 🤖 BOT Raise - رايس 🤖
[C]-----------------------
[C] ℹ️ اكتب [ !معلومات <منشن/رابط> ] لعرض معلومات العضو.
[C]-----------------------
[C] 🔨 اكتب [ حظر قروب <منشن/رابط> ] لحظر دائم.
[C]-----------------------
[C] 🔓 اكتب [ عفو عن <منشن/رابط> ] لإلغاء حظر القروب.
[C]-----------------------
[C] 🔕 اكتب [ كتم1/2/3 <منشن> ] لكتم العضو (ساعة/يوم/دائم).
[C]-----------------------
[C] 📢 اكتب [ فك الكتم <منشن> ] لإلغاء الكتم.
[C]-----------------------
[C] 🏃 اكتب [ طرد1/طرد2 <منشن> ] طرد عادي أو نهائي.
[C]-----------------------
[C] ⛔ اكتب [ !عرض ] أو [ إطلاع القروب ] لقفل الدردشة.
[C]-----------------------
[C] ✅ اكتب [ !فتح ] لفتح الدردشة.
[C]-----------------------
[C] 🗑️ اكتب [ !حذف ] (مع رد) لحذف رسالة.
[C]-----------------------
[C] 📌 اكتب [ !تثبيت ] (مع رد) لتثبيت رسالة.
[C]-----------------------
[C] 📣 اكتب [ منشن ] لمناداة الجميع.
[C]-----------------------
[C] ✨ اكتب [ قائمة المشرفين ] لعرض المشرفين الحاليين.
[C]-----------------------
[C] 👑 اكتب [ ترقيه إشراف <منشن> ] لإعطاء رتبة الإشراف. (للمطور)
[C]-----------------------
[C] 📉 اكتب [ ازاله إشراف <منشن> ] لإزالة رتبة الإشراف.
[C]-----------------------
[C] ➕ اكتب [ اضف قروب <رابط> ] لمراقبة قروب جديد. (للمطور)
[C]-----------------------
[C] ➖ اكتب [ ازالة قروب <رابط> ] لإلغاء مراقبة قروب. (للمطور)
[C]-----------------------
[C] 📜 اكتب [ قائمة القروبات ] لعرض القروبات المراقبة.
[C]-----------------------
[C] 🎮 اكتب [ العاب ] لعرض قائمة الألعاب.
[C]-----------------------
"""
                safe_send(sub, chat_id, menu, replyTo=mid)
                return

        
        if author_uid == DEV_UID and isinstance(txt, str) and txt.startswith("ارسل اعلان:"):
            announcement_text = txt.replace("ارسل اعلان:", "", 1).strip()
            if announcement_text:
                full_announcement = f"[BC]📢 إعلان المطور:\n{announcement_text}\n⚡️"
                threading.Thread(target=broadcast_message_all, args=(full_announcement,), daemon=True).start()
                safe_send(sub, chat_id, "✅ تم إرسال الإعلان لجميع القروبات المراقبة.", replyTo=mid)
            else:
                safe_send(sub, chat_id, "❌ يرجى إضافة نص الإعلان بعد 'ارسل اعلان:'.", replyTo=mid)
            return

        lowered = txt.lower()
        contains_name = any(alias in lowered for alias in BOT_ALIASES)

        if mentioned or reply_to_me or contains_name:
            search_text = txt
            for alias in BOT_ALIASES:
                search_text = re.sub(r'\b' + re.escape(alias) + r'\b', '', search_text, flags=re.IGNORECASE).strip()
            
            resp = search_in_responses(search_text, chatId=chat_id, threshold=0.5)
            
            if not resp:
                resp = get_default_response(chatId=chat_id)
            
            try:
                sub.send_message(chatId=chat_id, message=resp, replyTo=mid)
            except Exception:
                try:
                    safe_send(sub, chat_id, resp, replyTo=mid)
                except:
                    pass
            return
            
        if txt.strip() in qa_responses:
            resp = search_in_responses(txt.strip(), chatId=chat_id, threshold=1.0)
            if resp:
                try:
                    sub.send_message(chatId=chat_id, message=resp, replyTo=mid)
                except Exception:
                    try:
                        safe_send(sub, chat_id, resp, replyTo=mid)
                    except:
                        pass
                return

    except Exception as e:
        print("Error processing message:", e)
        traceback.print_exc()
        return

def broadcast_message_all(text):
    current_monitored = list(monitored_groups)
    for link in current_monitored:
        try:
            comId, objectId, full_link = get_chat_and_community_ids(link)
            if comId and objectId and full_link in monitored_groups:
                sub = amino.SubClient(comId=comId, profile=client.profile)
                try:
                    sub.send_message(chatId=objectId, message=text)
                    time.sleep(1) 
                except Exception:
                    pass
        except Exception:
            pass

def restart_program():
    print("جاري إعادة تشغيل البوت لتطبيق الإعدادات الجديدة...")
    
    threading.Thread(target=broadcast_message_all, 
                     args=("رايس يعيد التشغيل لتطبيق الأوامر الجديدة. ثواني وراجع لكم...",), 
                     daemon=True).start()
    
    time.sleep(2)

    try:
        python = sys.executable or "python"
        os.execv(python, [python] + sys.argv)
    except Exception:
        print("فشل إعادة التشغيل عبر execv، سيتم إنهاء البرنامج بدلاً من ذلك.")
        os._exit(0)

def monitor_loop_for_group(link):
    while True:
        try:
            comId, objectId, full_link = get_chat_and_community_ids(link)
            
            if not comId or not objectId:
                print(f"فشل جلب معلومات القروب {link}. سأحاول لاحقاً.")
                time.sleep(5)
                continue

            sub = amino.SubClient(comId=comId, profile=client.profile)
            chat_obj = {"objectId": objectId, "comId": comId}
            chat_id = objectId
            
            last_member_check = 0 
            
            while True:
                try:
                    
                    msgs = fetch_messages(sub, chat_id, size=1)
                    if msgs:
                        process_message(msgs[0], sub, chat_obj)
                    
                    
                    current_time = time.time()
                    if current_time - last_member_check >= 20.0: 
                        last_member_check = current_time

                        if hasattr(sub, "get_chat_members"):
                            members_resp = sub.get_chat_members(chatId=chat_id)
                            member_list = members_resp.get("memberList", []) if isinstance(members_resp, dict) else (members_resp or [])
                            chat_seen = set(seen_members_db.get(chat_id, []))
                            changed = False
                            
                            my_uid = getattr(getattr(client, "profile", {}), "userId", None)
                            
                            for m in member_list:
                                uid = m.get("uid") if isinstance(m, dict) else None
                                if not uid or uid == my_uid: continue
                                
                                
                                if uid not in chat_seen:
                                    chat_seen.add(uid)
                                    changed = True
                                    
                                    try:
                                        mention_user_in_message(sub, chat_id, uid, "مرحبا بك في المجموعة، منورنا يا شنب!")
                                    except:
                                        pass

                            if changed:
                                seen_members_db[chat_id] = list(chat_seen)
                                save_json(paths["seen"], seen_members_db)
                        
                    time.sleep(0.2) 

                except Exception as e:
                    print(f"خطأ داخل حلقة المراقبة للقروب {link}:", e)
                    traceback.print_exc()
                    time.sleep(2)
                    break
        except Exception as e:
            print(f"خطأ عام بمراقبة القروب {link}:", e)
            time.sleep(5)

def main():
    if 'keep_alive' in sys.modules and hasattr(keep_alive, 'keep_alive'):
        try:
            T(target=keep_alive.keep_alive, daemon=True).start()
            print("✅ تم تشغيل keep_alive.py بنجاح في خيط منفصل.")
        except Exception as e:
            print(f"❌ خطأ عند محاولة تشغيل دالة keep_alive() من keep_alive.py: {e}")
    else:
        print("❌ لم يتم العثور على ملف keep_alive.py أو الدالة keep_alive() بداخله. لن يتم تفعيل الحفاظ على التشغيل.")
    
    if not getattr(client, "profile", None):
        try_login()

    if not monitored_groups:
        print("لا يوجد قروبات للمراقبة. أضف رابط قروب واحد في قروبات.json")
        return

    threads = []
    for link in monitored_groups:
        t = T(target=monitor_loop_for_group, args=(link,), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(0.5)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("تم الإيقاف بواسطة المستخدم.")
    except Exception as e:
        print("خطأ في الخيط الرئيسي:", e)
        traceback.print_exc()

if __name__ == "__main__":
    main()
