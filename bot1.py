import os
import time
import threading
import json
import re
import random
import traceback
import difflib
import sys
import requests
from datetime import datetime

try:
    import aminodorksfix as amino
    from aminodorksfix.lib.util.exceptions import UnexistentData
except ImportError:
    import amino
    from amino.lib.util.exceptions import UnexistentData

try:
    import edge_tts
except ImportError:
    print("Missing 'edge-tts' library. Please install it: pip install edge-tts")
    sys.exit(1)
import asyncio

from threading import Thread as T
from random import choice, sample, randint
from num2words import num2words 

import games

EMAIL = "abosaeg8@gmail.com"
PASSWORD = "foo40k"
API_KEY = "1bd49e6563fb5b744a999b6c050197a9"
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"
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
    "banned": os.path.join(BASE_DIR, "محظورون.json"),
    "admins": os.path.join(BASE_DIR, "مشرفين.json"),
    "groups": os.path.join(BASE_DIR, "قروبات.json"),
    "bots": os.path.join(BASE_DIR, "bots.json"),
    "prize_queue": os.path.join(BASE_DIR, "prize_queue.json"), # <-- ملف الجوائز اليدوية
    "bank": os.path.join(BASE_DIR, "bank.json"), # <-- ملف أرباح الألعاب الجديد
}

VOICE = "ar-OM-AbdullahNeural"

async def _generate_tts_async(text, file_path):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(file_path)

def generate_tts_sync(text, file_path):
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_generate_tts_async(text, file_path))
    except Exception as e:
        print(f"Error in generate_tts_sync: {e}")
        raise e
    finally:
        if loop:
            loop.close()

# --- تهيئة الملفات ---
for k, p in paths.items():
    if not os.path.isfile(p):
        if p.endswith(".json"):
            # تحديد القيمة الأولية بناءً على اسم الملف
            if os.path.basename(p) in ("warnings.json", "banned.json", "admins.json", "prize_queue.json", "bank.json"):
                init = {}
            elif os.path.basename(p) == "قروبات.json":
                init = ["http://aminoapps.com/p/tqfa4v3"]
            else:
                init = [] # لبقية ملفات json مثل bots.json
                
            with open(p, "w", encoding="utf-8") as f:
                json.dump(init, f, ensure_ascii=False, indent=2)
        else:
            # لملفات .txt
            open(p, "w", encoding="utf-8").close()

def load_json(p):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # إرجاع القيمة الافتراضية الصحيحة إذا فشل التحميل
        if os.path.basename(p) in ("warnings.json", "banned.json", "admins.json", "prize_queue.json", "bank.json"):
            return {}
        return []

def save_json(p, d):
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, ensure_ascii=False, indent=2, fp=f)
    except Exception as e:
        print("Save error", p, e)

# --- تحميل قواعد البيانات ---
warnings_db = load_json(paths["warnings"])
local_banned = load_json(paths["banned"])
admins_db = load_json(paths["admins"])
monitored_groups = load_json(paths["groups"]) or []
bots_db = load_json(paths["bots"])
prize_queue = load_json(paths["prize_queue"]) # <-- قائمة الدعم اليدوي
bank_db = load_json(paths["bank"]) # <-- بنك أرباح الألعاب

# --- متغيرات نظام الجوائز (اليدوية) ---
prize_send_count = 0
prize_system_paused = False
prize_system_lock = threading.Lock()
# ------------------------------

# --- قفل خاص ببنك الألعاب ---
bank_lock = threading.Lock()
# ------------------------------

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

client = amino.Client(api_key=API_KEY)

def try_login(retries=6, delay=3):
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

last_message_processed = {}
message_processing_lock = threading.Lock()
last_response_position = {}


def call_gemini(prompt_text):
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        return "[C] خدمة الذكاء الاصطناعي غير مفعّلة حالياً."
    try:
        url = "https://generativelace.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": GEMINI_API_KEY}
        data = {"contents": [{"parts": [{"text": prompt_text}]}]}
        response = requests.post(url, headers=headers, params=params, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"].replace("*", "").replace("\"", "").strip()
    except Exception as e:
        print(f"خطأ في Gemini: {e}")
        return "[C] فشل الاتصال بخدمة Gemini."

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
    if uid == DEV_UID: return
    local_banned.pop(uid, None)
    save_json(paths["banned"], local_banned)

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

def kick_user(sub, uid, chatId=None, temporary=True):
    if uid == DEV_UID:
        return False

    methods = []
    if temporary:
        methods = [
            lambda: sub.kick(chatId=chatId, userId=uid, allowRejoin=True),
            lambda: client.kick(chatId=chatId, userId=uid, allowRejoin=True)
        ]
    else:
        methods = [
            lambda: sub.kick(chatId=chatId, userId=uid, allowRejoin=False),
            lambda: client.kick(chatId=chatId, userId=uid, allowRejoin=False),
            lambda: sub.ban(chatId=chatId, userId=uid),
            lambda: client.ban(chatId=chatId, userId=uid)
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

def kick_user_from_all_chats(target_uid):
    if target_uid == DEV_UID: return [], []
    
    kicked_from = []
    failed_in = []
    
    current_monitored = list(monitored_groups)
    for link in current_monitored:
        try:
            comId, objectId, full_link = get_chat_and_community_ids(link)
            if comId and objectId:
                sub = amino.SubClient(comId=comId, profile=client.profile)
                
                if kick_user(sub, target_uid, chatId=objectId, temporary=True):
                    kicked_from.append(objectId)
                else:
                    failed_in.append(objectId)
                time.sleep(1) 
        except Exception:
            failed_in.append(link)
    print(f"Global kick for {target_uid}: Success in {len(kicked_from)} chats, Failed in {len(failed_in)} chats.")
    return kicked_from, failed_in

def is_supervisor(uid):
    if uid == DEV_UID:
        return True
    if isinstance(admins_db, dict):
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
        msg = f"⚠️ لا أستطيع تنفيذ أي أمر ضد المطور، حساب المطور: {DEV_LINK}"
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

def collect_all_uids(sub, chat_id):
    all_users = []
    start = 0
    size = 100
    max_members = 1000 
    
    while len(all_users) < max_members:
        try:
            users_resp = sub.get_chat_users(chatId=chat_id, start=start, size=size)
            
            user_list = users_resp.userProfileList if hasattr(users_resp, 'userProfileList') else (getattr(users_resp, 'json', []) or [])

            if not user_list:
                break
            
            users_in_chunk = []
            for user in user_list:
                if isinstance(user, dict) and user.get("uid"):
                    uid = user.get("uid")
                    nickname = user.get("nickname", "User") 
                    users_in_chunk.append((uid, nickname))
                elif hasattr(user, 'uid'):
                    uid = getattr(user, 'uid')
                    nickname = getattr(user, 'nickname', 'User')
                    users_in_chunk.append((uid, nickname))

            all_users.extend(users_in_chunk)
            
            start += size
            if len(user_list) < size:
                break
        except Exception as e:
            print(f"Error collecting chat members: {e}")
            break
            
    return all_users

def mention_everyone_in_chat(sub, chatId, replyTo=None, message_text="منشن من رايس"):
    try:
        all_users = collect_all_uids(sub, chatId)
        my_uid = getattr(getattr(client, "profile", {}), "userId", None)
        
        all_users_filtered = [u for u in all_users if u[0] != my_uid]

        if not all_users_filtered or len(all_users_filtered) < 2:
            count = len(all_users_filtered)
            safe_send(sub, chatId, f"[C] تعذر عمل منشن، العدد الحالي هو {count}، يجب أن يكون 2 على الأقل.", replyTo=replyTo)
            return False
        
        total_members = len(all_users_filtered)
        chunk_size = 100 

        for i in range(0, total_members, chunk_size):
            chunk = all_users_filtered[i:i + chunk_size]
            
            chunk_uids = [u[0] for u in chunk] 
            chunk_nicknames = [f"@{u[1]}" for u in chunk]
            
            chunk_num = (i // chunk_size) + 1
            
            if i == 0:
                prefix_msg = f"[C] {message_text}\n[C] جاري عمل منشن لـ {total_members} عضو. الدفعة {chunk_num}:\n"
            else:
                prefix_msg = f"[C] [تكملة المنشن] الدفعة {chunk_num}:\n"
                
            chunk_content = prefix_msg + " ".join(chunk_nicknames)
            
            for attempt in range(3):
                try:
                    sub.send_message(
                        chatId=chatId, 
                        message=chunk_content, 
                        mentionUserIds=chunk_uids,
                        replyTo=replyTo if i == 0 else None
                    ) 
                    time.sleep(1) 
                    break
                except Exception as e:
                    print(f"Error during mention chunk {chunk_num}: {e}")
                    time.sleep(2)
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
        "ترا ما نمtت، وش بغيت؟",
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
            uids = list(admins_db.keys())
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

# --- 
# --- !!! نظام الجوائز اليدوي (للمشرفين) !!!
# ---

def add_to_prize_queue(uid, amount):
    """(يدوي) إضافة جائزة إلى قائمة الانتظار (آمنة للخيوط)"""
    global prize_queue
    try:
        if not isinstance(prize_queue, dict):
            prize_queue = {}
        prize_queue[uid] = prize_queue.get(uid, 0) + amount
        save_json(paths["prize_queue"], prize_queue)
        print(f"Added {amount} coins for UID {uid} to prize queue.")
    except Exception as e:
        print(f"Error in add_to_prize_queue: {e}")

def reset_prize_pause():
    """(يدوي) إعادة تعيين عداد الجوائز بعد انتهاء فترة التوقف"""
    global prize_system_paused, prize_send_count, prize_system_lock
    with prize_system_lock:
        prize_system_paused = False
        prize_send_count = 0
        print("Prize system pause lifted. Ready to award again.")

def send_coins_to_global_post(uid, amount):
    """
    (عالمي) يبحث عن آخر منشور عالمي للعضو ويرسل له القروش.
    يرجع (True, "global_post") أو (False, "error_message")
    """
    try:
        blogs = client.get_user_blogs(userId=uid, start=0, size=1)
        if blogs and isinstance(blogs, dict) and blogs.get("blogList"):
            first_blog = blogs["blogList"][0]
            g_comId = first_blog.get("ndcId") # ndcId هو comId
            g_blogId = first_blog.get("blogId")
            
            if g_comId and g_blogId:
                print(f"Found GLOBAL blogId: {g_blogId} in comId: {g_comId} for {uid}")
                temp_sub = amino.SubClient(comId=g_comId, profile=client.profile)
                temp_sub.send_coins(blogId=g_blogId, coins=amount)
                return True, "global_post"
        
        print(f"No GLOBAL blog found for {uid}")
        return False, "not_found"
        
    except Exception as e:
        print(f"Error in send_coins_to_global_post for {uid}: {e}")
        return False, str(e)


def award_prize(sub, uid, amount, chat_id_for_report=None):
    """(يدوي) الدالة الرئيسية لمنح الجوائز (مع نظام التوقف وقائمة الانتظار)"""
    global prize_system_paused, prize_send_count, prize_system_lock
    
    if not uid or not amount or not sub:
        return

    try:
        nickname = get_user_nickname(uid) or uid
        
        with prize_system_lock:
            if prize_system_paused:
                add_to_prize_queue(uid, amount)
                if chat_id_for_report:
                    safe_send(sub, chat_id_for_report, f"مبروك {nickname}! تم إضافة {amount} قرش إلى رصيدك (في قائمة الانتظار بسبب الضغط).")
                return

            if prize_send_count >= 10:
                prize_system_paused = True
                threading.Timer(300.0, reset_prize_pause).start() # 5 دقائق
                add_to_prize_queue(uid, amount)
                print("Prize system paused for 5 minutes (10 prizes sent).")
                if chat_id_for_report:
                    safe_send(sub, chat_id_for_report, f"مبروك {nickname}! تم إضافة {amount} قرش إلى رصيدك (في قائمة الانتظار بسبب الضغط).")
                return

            success, method = send_coins_to_global_post(uid, amount)
            
            if success:
                prize_send_count += 1
                print(f"Successfully sent {amount} coins to {uid} ({method}) (Count: {prize_send_count}/10)")
                if chat_id_for_report:
                    safe_send(sub, chat_id_for_report, f"🎉 مبروك {nickname}! تم إرسال {amount} قرش كجائزة إلى منشورك العالمي!")
            else:
                print(f"Global send method failed for {uid}. Adding to queue.")
                add_to_prize_queue(uid, amount)
                if chat_id_for_report:
                    safe_send(sub, chat_id_for_report, f"مبروك {nickname}! تعذر إرسال {amount} قرش (خطأ بالدعم). تم حفظها لك.")
                
    except Exception as e:
        print(f"Error in award_prize: {e}")
        add_to_prize_queue(uid, amount) # حفظ الجائزة كإجراء احتياطي

def process_prize_queue(sub, chat_id):
    """(يدوي) معالجة قائمة الانتظار للجوائز (أمر !دعم المستحقين)"""
    global prize_queue
    
    if not isinstance(prize_queue, dict) or not prize_queue:
        safe_send(sub, chat_id, "ℹ️ قائمة المستحقين (اليدوية) فارغة.")
        return

    queue_copy = dict(prize_queue) # نسخة للعمل عليها
    success_count = 0
    fail_count = 0
    
    for uid, amount in queue_copy.items():
        if amount <= 0: # تخطي المبالغ الصفرية
            prize_queue.pop(uid, None)
            continue
            
        success, method = send_coins_to_global_post(uid, amount)
        
        if success:
            prize_queue.pop(uid, None) # نجح، احذفه من الطابور
            success_count += 1
            print(f"Queue: Successfully sent {amount} to {uid} ({method})")
            time.sleep(1) # لتجنب الحظر
        else:
            print(f"Queue: Global send method failed for {uid}")
            fail_count += 1
    
    save_json(paths["prize_queue"], prize_queue) # حفظ القائمة المحدثة
    safe_send(sub, chat_id, f"✅ اكتمل دعم المستحقين:\n- تم دعم: {success_count} أعضاء.\n- فشل/مؤجل: {fail_count} أعضاء (لا يزالون في القائمة).")

# ------------------------------------------

# --- 
# --- !!! نظام بنك الألعاب (تلقائي) !!!
# ---

def update_bank_balance(uid, nickname, amount_to_add):
    """(تلقائي) تحديث رصيد الفائز في بنك الألعاب (آمن للخيوط)"""
    global bank_db
    if not uid or not nickname or not amount_to_add:
        return
        
    with bank_lock:
        if not isinstance(bank_db, dict):
            bank_db = {}
            
        if uid not in bank_db:
            bank_db[uid] = {"nickname": nickname, "coins": 0}
        
        bank_db[uid]["coins"] = bank_db[uid].get("coins", 0) + amount_to_add
        bank_db[uid]["nickname"] = nickname # تحديث الاسم دائماً
        
        save_json(paths["bank"], bank_db)
        print(f"Bank updated for {uid} ({nickname}): Added {amount_to_add}, New total: {bank_db[uid]['coins']}")

def get_bank_balance(uid):
    """(تلقائي) جلب رصيد بنك الألعاب للعضو"""
    if not isinstance(bank_db, dict):
        return 0
    return bank_db.get(uid, {}).get("coins", 0)

def clear_bank_balance(uid):
    """(تلقائي) تصفير رصيد بنك الألعاب للعضو بعد السحب"""
    global bank_db
    with bank_lock:
        if uid in bank_db:
            bank_db[uid]["coins"] = 0
            save_json(paths["bank"], bank_db)
            print(f"Bank balance cleared for {uid}")

# ------------------------------------------

bot_context = {
    "fetch_messages": fetch_messages,
    "get_user_nickname": get_user_nickname,
    "is_supervisor": is_supervisor,
    "generate_tts_sync": generate_tts_sync,
    "BASE_DIR": BASE_DIR,
    "VOICE": VOICE,
    "update_bank_balance": update_bank_balance, # <-- تمرير دالة بنك الألعاب
}

def process_message(m, sub, chat_obj):
    global admins_db 
    global prize_queue 
    global bank_db # جلب المتغير العام
    try:
        mid = m.get("messageId")
        author = m.get("author") or {}
        if isinstance(author, dict):
            author_uid = author.get("uid")
            author_nickname = author.get("nickname", "عضو")
        else:
            author_uid = getattr(author, "uid", None)
            author_nickname = getattr(author, "nickname", "عضو")


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
            try:
                delete_message(sub, mid, chatId=chat_id)
            except Exception:
                pass
            return

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
            deletion_succeeded = False
            try:
                deletion_succeeded = delete_message(sub, mid, chatId=chat_id)
            except Exception:
                deletion_succeeded = False
            
            if deletion_succeeded:
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
                    success = kick_user(sub, author_uid, chatId=chat_id, temporary=False)
                    
                    warnings_db[chat_id][author_uid]["count"] = 0
                    warnings_db[chat_id][author_uid].pop("status", None) 
                    save_json(paths["warnings"], warnings_db)
                    
                    if not success:
                        kick_user(sub, author_uid, chatId=chat_id, temporary=True) 
                
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
            
            else:
                safe_send(sub, chat_id, "عيب تسب ماني كو ولا كان لقمتك", replyTo=mid)

            return
        
        if is_local_banned(author_uid):
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
        
        # --- متغيرات الأوامر النصية ---
        txt_str = txt
        txt_lower = txt.strip().lower()
        txt_strip = txt.strip()
            
        if games.handle_game_command(sub, txt_lower, author_uid, chat_id, mid, BOT_NAME_AR, bot_context):
            return

        # --- أمر !بنكي (الجديد) ---
        if txt_strip == "!بنكي":
            user_balance = get_bank_balance(author_uid)
            
            if user_balance > 0:
                bank_msg = f"""[BC]🏦 بنك رايس 🏦
[C]-----------------------
[C]👤 العضو: {author_nickname}
[C]🆔 الآي دي: {author_uid}
[C]💰 الرصيد الحالي: {user_balance} قروش
[C]-----------------------
[C]لسحب أرباحك، اكتب:
[C]سحب قروشي <رابط منشورك>"""
            else:
                bank_msg = "ليس لديك أرباح — العب لتربح"
            
            safe_send(sub, chat_id, bank_msg, replyTo=mid)
            return

        # --- أمر سحب القروش (الجديد) ---
        if txt_lower.startswith("سحب قروشي"):
            user_balance = get_bank_balance(author_uid)
            
            if user_balance <= 0:
                safe_send(sub, chat_id, "ليس لديك ارباح لسحبها", replyTo=mid)
                return

            user_link_match = re.search(r'(http://aminoapps\.com/p/[a-zA-Z0-9]+)', txt)
            if not user_link_match:
                safe_send(sub, chat_id, "❌ يرجى إرفاق رابط منشور أو ويكي لسحب القروش.", replyTo=mid)
                return
            
            link = user_link_match.group(0)
            target_blog_id = None
            target_wiki_id = None
            
            try:
                obj = client.get_from_code(link)
                if obj.objectType == 1: # Blog
                    target_blog_id = obj.objectId
                elif obj.objectType == 3: # Wiki
                    target_wiki_id = obj.objectId
                else:
                    safe_send(sub, chat_id, "❌ الرابط غير صالح. يرجى إرسال رابط منشور أو ويكي.", replyTo=mid)
                    return
            except Exception as e:
                safe_send(sub, chat_id, f"❌ فشل التعرف على الرابط: {e}", replyTo=mid)
                return

            try:
                if target_blog_id:
                    sub.send_coins(blogId=target_blog_id, coins=user_balance)
                elif target_wiki_id:
                    sub.send_coins(wikiId=target_wiki_id, coins=user_balance)
                
                # نجح الإرسال، قم بتصفير الرصيد
                clear_bank_balance(author_uid)
                safe_send(sub, chat_id, f"✅ تم ارسال قروشك بالكامل ({user_balance} قرش). عدد قروشك الأن 0", replyTo=mid)

            except Exception as e:
                safe_send(sub, chat_id, f"❌ فشل إرسال القروش. تأكد من أن الرابط صحيح وأنني أمتلك قروشًا كافية. الخطأ: {e}", replyTo=mid)
            
            return

        if isinstance(txt, str) and txt.startswith("معلومات"):
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
                com_profile_raw = sub.get_user_info(target_uid)
                glob_profile_raw = client.get_user_info(target_uid)

                if not isinstance(com_profile_raw, dict):
                    com_profile = com_profile_raw.__dict__
                else:
                    com_profile = com_profile_raw.get('userProfile', com_profile_raw)
                
                if not isinstance(glob_profile_raw, dict):
                    glob_profile = glob_profile_raw.__dict__
                else:
                    glob_profile = glob_profile_raw.get('userProfile', glob_profile_raw)


                nickname = com_profile.get("nickname", "N/A")
                level = com_profile.get("level", "N/A")
                reputation = com_profile.get("reputation", "N/A")
                
                created_time_str = com_profile.get("createdTime", "N/A")
                join_date = "N/A"
                if created_time_str != "N/A":
                     try:
                        join_date = created_time_str.split('T')[0]
                     except:
                        join_date = created_time_str 
                
                com_followers = com_profile.get("followersCount", "N/A")
                com_following = com_profile.get("followingCount", "N/A")
                com_posts = com_profile.get("postsCount", "N/A")
                com_wikis = com_profile.get("wikiCount", "N/A")
                com_wall_comments = com_profile.get("commentsCount", "N/A")
                

                glob_followers = glob_profile.get("followersCount", "N/A")
                glob_following = glob_profile.get("followingCount", "N/A")
                glob_posts = glob_profile.get("postsCount", "N/A")
                glob_wall_comments = glob_profile.get("commentsCount", "N/A")


                message = f"""[BC]— ملف العضو: {nickname} —

[C]المستوى: {level}
[C]السمعة: {reputation}
[C]تاريخ الانضمام: {join_date}
[C]UID: {target_uid}

[C]— إحصائيات المنتدى —
[C]المتابعون: {com_followers}
[C]يُتابِع: {com_following}
[C]المنشورات: {com_posts}
[C]تعليقات الحائط: {com_wall_comments}

[C]— إحصائيات عالمية —
[C]المتابعون (عام): {glob_followers}
[C]يُتابِع (عام): {glob_following}
[C]المنشورات (عام): {glob_posts}
[C]تعليقات الحائط (عام): {glob_wall_comments}"""
                safe_send(sub, chat_id, message, replyTo=mid)
            
            except Exception as e:
                print(f"Error in 'معلومات' command for UID {target_uid}: {e}") 
                safe_send(sub, chat_id, "❌ فشل جلب معلومات العضو. قد يكون هناك خطأ في الخادم. حاول مرة أخرى.", replyTo=mid)

            return
            
        if isinstance(txt, str) and txt.strip() in ("قائمة المشرفين", "قائمة_المشرفين", "مشرفين"):
            
            if not isinstance(admins_db, dict) or not admins_db:
                safe_send(sub, chat_id, "ما عندنا مشرفين حالياً.", replyTo=mid)
                return
                
            out_lines = ["[BC]المعلمين (مشرفي البوت) هم:"]
            for uid, info in admins_db.items():
                nickname = info.get("nickname") or "اسم غير متوفر" 
                link = info.get("link", "")          
                
                out_lines.append(f"[C]- {nickname}")
                if link:
                    out_lines.append(f"[C]{link}")

            safe_send(sub, chat_id, "\n".join(out_lines), replyTo=mid)
            return
            
        if isinstance(txt, str) and txt.strip() == "انضمام":
            join_message = """[BC]لأنضمام البوت الى قروبك:🤖
[C]ضع رابطها هنا: http://aminoapps.com/p/v1dtcyg"""
            safe_send(sub, chat_id, join_message, replyTo=mid)
            return

        if isinstance(txt, str) and txt.strip() in ("المطور", "مطور البوت"):
            mention_user_in_message(sub, chat_id, DEV_UID, f"هذا هو المطور: {DEV_LINK}", replyTo=mid)
            return
            
        if isinstance(txt, str) and txt.strip() in ("الأوامر", "القائمة","قائمة","الاوامر"):
            
            menu = """[BC]🤖 BOT Raise - قائمة الأوامر 🤖
[C]---------------------------------------          
[BC]أوامر الأعضاء👫
[C]---------------------------------------
[C][اكتب معلومات@منشن/رابط](لعرض معلومات العضو)ℹ️
[C]🎮 [ العاب ] (لعرض قائمة الألعاب)
[C]🏦 [ !بنكي ] (لعرض رصيد أرباحك من الألعاب)
[C]💸 [ سحب قروشي <رابط> ] (لسحب أرباح الألعاب)
[C]🔄 [ انضمام ] ( لرؤية طريقة إضافة البوت لقروبك)
[C]🔰 [ مشرفين ] (لعرض مشرفي البوت)
[C] 👑 (المطور او مطور البوت) [ لظهور رابط حساب المطور ]
[BC]أوامر مشرفي البوت🔰
[C]---------------------------------------
[C] 💰 [ kroh <العدد> قروب ] (إرسال قروش للقروب)
[C] 💰 [ kroh <العدد> <رابط منشور> ] (إرسال قروش للمنشور)
[C] 🎁 [ !دعم المستحقين ] (إرسال الجوائز اليدوية العالقة)
[C] 🔨 [ Blok <منشن/رابط> ] (للحذف التلقائي)
[C]🔓 [ Blok A <منشن/رابط> ] (لإلغاء الحذف التلقائي)
[C] 📌 [ !رفع اعلان: >نص ] (لتعيين إعلان للقروب)
[C] 📌 [ !رفع اعلان ] (برد على رسالة لتعيينها إعلان)
[C] 🗑️ [ !احذف الإعلان ] (لمسح الإعلان المثبت)
[C] 🔒 [ !اطلاع ] (تفعيل وضع القراءة فقط)
[C] ✅ [ !فتح ] (إلغاء وضع الاطلاع)
[C] 🗑️ [ !حذف ] (مع رد لحذف رسالة)
[C] 🔕 [ K1/K2/K3 <منشن> ] (لكتم العضو)
[C] 📢 [ KA <منشن> ] (لإلغاء الكتم)
[C] 🏃 [ Tar1/Tae2 <منشن> ] (طرد مؤقت أو نهائي)
[C] 📜 [ قائمة القروبات ] (لعرض القروبات المراقبة)
[C] ✈️ [ Tar raes <منشن> ] (طرد العضو من جميع القروبات)
[BC]أوامر المطور👑 
[C]---------------------------------------
[C] 📣 [ منشن ] (لمناداة الجميع)
[C] 🔰 [ Ahr <منشن> ] (لإعطاء إشراف بوت)
[C] 📉 [ Tn Ahr <منشن> ] (لإزالة إشراف بوت)
[C] ➕ [ اضف قروب <رابط> ] (لمراقبة قروب جديد)
[C] ➖ [ ازالة قروب <رابط> ] (لإلغاء مراقبة قروب)"""
            safe_send(sub, chat_id, menu, replyTo=mid)
            return

        author_is_supervisor = is_supervisor(author_uid)
        author_is_dev = (author_uid == DEV_UID)
        author_is_supervisor_or_dev = author_is_supervisor or author_is_dev
        
        author_has_chat_power = author_is_supervisor_or_dev
        
        if author_has_chat_power:
            
            # --- أوامر القروش والجوائز (اليدوية) ---
            if txt_strip == "!دعم المستحقين":
                safe_send(sub, chat_id, "🔁 جاري محاولة دعم المستحقين (القائمة اليدوية) في الخلفية...", replyTo=mid)
                threading.Thread(target=process_prize_queue, args=(sub, chat_id), daemon=True).start()
                return

            # --- !!! تعديل أمر kroh !!! ---
            if txt_lower.startswith("kroh") or txt_lower.startswith("hroh"):
                try:
                    parts = txt.split()
                    if len(parts) < 2:
                        raise ValueError("Invalid format")
                    
                    amount_str = re.sub(r'\D', '', parts[1])
                    if not amount_str: 
                        amount_str = re.sub(r'\D', '', parts[0])
                    amount = int(amount_str)
                    
                    if amount <= 0:
                        raise ValueError("Invalid amount")

                    # تمت إزالة target_uid
                    target_blog_id = None
                    target_wiki_id = None 
                    target_chat_id = None

                    # تمت إزالة mentioned_list و user_ndc_match
                    user_link_match = re.search(r'(http://aminoapps\.com/p/[a-zA-Z0-9]+)', txt)

                    if user_link_match:
                        link = user_link_match.group(0)
                        try:
                            obj = client.get_from_code(link)
                            if obj.objectType == 1: # Blog
                                target_blog_id = obj.objectId
                            elif obj.objectType == 3: # Wiki
                                target_wiki_id = obj.objectId
                            # تم حذف الشرط الخاص بـ obj.objectType == 0 (User)
                            elif obj.objectType == 12: # Chat
                                target_chat_id = obj.objectId
                        except:
                            pass 
                    
                    if "قروب" in txt_lower:
                        target_chat_id = chat_id
                    elif not target_blog_id and not target_wiki_id and not target_chat_id:
                        # الافتراضي هو القروب إذا لم يتم تحديد رابط
                        target_chat_id = chat_id
                    
                    # --- تنفيذ الإرسال ---
                    if target_blog_id:
                        sub.send_coins(blogId=target_blog_id, coins=amount)
                        safe_send(sub, chat_id, f"✅ تم إرسال {amount} قرش إلى المنشور.", replyTo=mid)
                    elif target_wiki_id:
                        sub.send_coins(wikiId=target_wiki_id, coins=amount)
                        safe_send(sub, chat_id, f"✅ تم إرسال {amount} قرش إلى الويكي.", replyTo=mid)
                    
                    # تم حذف الشرط الخاص بـ target_uid
                    
                    elif target_chat_id:
                        sub.send_coins(chatId=target_chat_id, coins=amount)
                        safe_send(sub, chat_id, f"✅ تم إرسال {amount} قرش إلى هذا القروب.", replyTo=mid)
                    else:
                        safe_send(sub, chat_id, "❌ لم أستطع تحديد الهدف (رابط منشور/ويكي، أو 'قروب').", replyTo=mid)

                except ValueError:
                    safe_send(sub, chat_id, "❌ صيغة خاطئة. استخدم: `kroh <العدد> [رابط/قروب]`", replyTo=mid)
                except Exception as e:
                    safe_send(sub, chat_id, f"❌ فشل إرسال القروش: {e}", replyTo=mid)
                return
            # --- نهاية أوامر القروش ---

            if txt_strip in ("!فتح_الدردشة", "!فتح"):
                done = False
                try:
                    sub.edit_chat(chatId=chat_id, viewOnly=False)
                    done = True
                except Exception as e:
                    print(f"Error opening chat (viewOnly=False): {e}")
                    pass
                safe_send(sub, chat_id, "✅ تم فتح الدردشة (إلغاء وضع الاطلاع)." if done else "❌ فشل فتح الدردشة. تأكد من صلاحياتي.", replyTo=mid)
                return

            if txt_strip == "!اطلاع":
                done = False
                err_str = "" 
                try:
                    sub.edit_chat(chatId=chat_id, viewOnly=True)
                    done = True
                except Exception as e:
                    print(f"Error setting viewOnly=True: {e}")
                    err_str = str(e) 
                    pass
                
                if "Connection reset by peer" in err_str or "104" in err_str:
                    done = True 
                
                safe_send(sub, chat_id, "✅ تم تفعيل وضع الاطلاع (القراءة فقط)." if done else "❌ فشل تفعيل وضع الاطلاع. تأكد من صلاحياتي.", replyTo=mid)
                return

            if txt_strip == "!حذف":
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

            if txt_strip in ("!أزل الإعلان", "!احذف الإعلان"):
                done = False
                try:
                    sub.edit_chat(chatId=chat_id, announcement="", pinAnnouncement=False)
                    done = True
                except Exception as e:
                    print(f"Error removing announcement: {e}")
                    pass
                safe_send(sub, chat_id, "✅ تم حذف الإعلان وفك تثبيته." if done else "❌ فشل حذف الإعلان. تأكد من صلاحياتي.", replyTo=mid)
                return

            if txt_lower.startswith("blok a"):
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
                        
                    mention_user_in_message(sub, chat_id, target_uid, "تم العفو عنه وإلغاء حذف الرسائل.", replyTo=mid)
                    
                else:
                    safe_send(sub, chat_id, "❌ العضو ليس لديه حالة حذف تلقائي.", replyTo=mid)
                return

            
            if txt_lower.startswith("blok") and not txt_lower.startswith("blok a"):
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

                final_msg = "تم تفعيل الحذف التلقائي لرسائل العضو."
                
                if chat_id not in warnings_db: warnings_db[chat_id] = {}
                if target_uid not in warnings_db[chat_id]: warnings_db[chat_id][target_uid] = {"count": 0, "last_bad": "", "status": None}
                warnings_db[chat_id][target_uid]["status"] = "group_banned"
                save_json(paths["warnings"], warnings_db)
                
                mention_user_in_message(sub, chat_id, target_uid, final_msg, replyTo=mid)

                return

            if "!رفع اعلان" in txt_str or "!تعديل اعلان" in txt_str:
                announcement_text = None
                
                if txt_str.startswith("!رفع اعلان:") or txt_str.startswith("!تعديل اعلان:"):
                    announcement_text = txt_str.split(":", 1)[-1].strip()
                
                elif txt_strip == "!رفع اعلان" or txt_strip == "!تعديل اعلان":
                    reply_msg = exts.get("replyMessage")
                    if isinstance(reply_msg, dict):
                        announcement_text = reply_msg.get("content")
                
                if announcement_text:
                    done = False
                    try:
                        sub.edit_chat(chatId=chat_id, announcement=announcement_text, pinAnnouncement=True)
                        done = True
                    except Exception as e:
                        print(f"Error setting announcement: {e}")
                        safe_send(sub, chat_id, f"❌ فشل رفع الإعلان. تأكد من صلاحياتي. (الخطأ: {e})", replyTo=mid)
                        return
                    
                    if done:
                        safe_send(sub, chat_id, "✅ تم رفع الإعلان وتثبيته.", replyTo=mid)
                    else:
                        safe_send(sub, chat_id, "❌ فشل رفع الإعلان. تأكد من صلاحياتي.", replyTo=mid)
                else:
                    safe_send(sub, chat_id, "❌ لاستخدام الأمر:\n- `!رفع اعلان: النص هنا`\n- أو رد على رسالة واكتب `!رفع اعلان`", replyTo=mid)
                return
        
        if author_is_supervisor_or_dev:
            
            mentioned_list_k = exts.get("mentionedArray", [])
            if mentioned_list_k and (txt_lower.startswith("k1") or txt_lower.startswith("k2") or txt_lower.startswith("k3")):
                uid_to_mute = mentioned_list_k[0].get("uid")
                if not uid_to_mute: return

                if check_command_protection(author_uid, uid_to_mute, chat_id, mid, sub): return

                if txt_lower.startswith("k1"):
                    add_local_ban(uid_to_mute, 3600)
                    safe_send(sub, chat_id, "تم الكتم لن أرد عليه لمده ساعة", replyTo=mid)
                elif txt_lower.startswith("k2"):
                    add_local_ban(uid_to_mute, 86400)
                    safe_send(sub, chat_id, "تم الكتم لمدة لمدة 24 ساعة", replyTo=mid)
                elif txt_lower.startswith("k3"):
                    add_local_ban(uid_to_mute, None)
                    safe_send(sub, chat_id, "تم الكتم لن أرد عليه للأبد", replyTo=mid)
                return

            
            mentioned_list_ka = exts.get("mentionedArray", [])
            if mentioned_list_ka and txt_lower.startswith("ka"):
                uid_to_unmute = mentioned_list_ka[0].get("uid")
                if not uid_to_unmute: return

                if check_command_protection(author_uid, uid_to_unmute, chat_id, mid, sub): return
                
                remove_local_ban(uid_to_unmute)
                safe_send(sub, chat_id, "تم فك الكتم عنه برد علية الأن.", replyTo=mid)
                return

            mentioned_list_t = exts.get("mentionedArray", [])
            if mentioned_list_t and (txt_lower.startswith("tar1") or txt_lower.startswith("tae2")):
                uid_to_kick = mentioned_list_t[0].get("uid")
                if not uid_to_kick: return

                if check_command_protection(author_uid, uid_to_kick, chat_id, mid, sub): return
                
                try:
                    if txt_lower.startswith("tar1"):
                        ok = kick_user(sub, uid_to_kick, chatId=chat_id, temporary=True)
                        safe_send(sub, chat_id, "تم الطرد المؤقت." if ok else "فشل الطرد.", replyTo=mid)
                    
                    elif txt_lower.startswith("tae2"):
                        ok = kick_user(sub, uid_to_kick, chatId=chat_id, temporary=False)
                        
                        if ok:
                            safe_send(sub, chat_id, "تم الطرد النهائي من القروب", replyTo=mid)
                        else:
                            ok2 = kick_user(sub, uid_to_kick, chatId=chat_id, temporary=True)
                            if ok2:
                                safe_send(sub, chat_id, "فشل الطرد النهائي، تم الطرد المؤقت بدلاً عنه.", replyTo=mid)
                            else:
                                safe_send(sub, chat_id, "فشل الطرد.", replyTo=mid)
                except Exception as e:
                    safe_send(sub, chat_id, f"فشل الطرد: {e}", replyTo=mid)
                return

            mentioned_list_tr = exts.get("mentionedArray", [])
            if mentioned_list_tr and txt_lower.startswith("tar raes"):
                target_uid = mentioned_list_tr[0].get("uid")
                if not target_uid:
                    safe_send(sub, chat_id, "❌ لم أجد العضو.", replyTo=mid)
                    return

                if check_command_protection(author_uid, target_uid, chat_id, mid, sub): return

                safe_send(sub, chat_id, f"🔁 جاري تنفيذ الطرد العام للعضو... قد يستغرق هذا بعض الوقت.", replyTo=mid)

                def global_kick_thread(uid, reply_chat_id, reply_mid):
                    kicked, failed = kick_user_from_all_chats(uid)
                    safe_send(sub, reply_chat_id, f"✅ اكتمل الطرد العام:\n- تم الطرد من {len(kicked)} قروب.\n- فشل الطرد في {len(failed)} قروب (قد لا أملك صلاحيات).", replyTo=reply_mid)
                
                threading.Thread(target=global_kick_thread, args=(target_uid, chat_id, mid), daemon=True).start()
                return

            if txt_strip in ("قائمة القروبات", "قروبات", "قائمة_القروبات"):
                gl = monitored_groups
                safe_send(sub, chat_id, "القروبات اللي أراقبها:\n" + ("\n".join(gl) if gl else "ما أراقب ولا قروب حالياً."), replyTo=mid)
                return

        if author_is_dev:
            if txt_strip in ("منشن", "منشن_الكل"):
                ok = mention_everyone_in_chat(sub, chat_id, replyTo=mid, message_text="يا جماعة الخير، أحد المشرفين يبغاكم.")
                if not ok:
                    safe_send(sub, chat_id, "فشل المنشن أو العدد قليل.", replyTo=mid)
                return

            if txt_str.lower().startswith("ahr"):
                mentioned_list = exts.get("mentionedArray", [])
                if not mentioned_list:
                    safe_send(sub, chat_id, "❌ منشن المستخدم يا مطوري العزيز.", replyTo=mid)
                else:
                    for u in mentioned_list:
                        uid = u.get("uid")
                        if uid:
                            nickname = u.get("nickname", uid)
                            if not isinstance(admins_db, dict):
                                admins_db = {}
                            
                            admins_db[uid] = {
                                "nickname": nickname,
                                "link": "" 
                            }
                            save_json(paths["admins"], admins_db)
                            
                            try:
                                sub.promote(userId=uid)
                            except:
                                pass
                            safe_send(sub, chat_id, f"✅ مبروك تمت ترقيته إشراف، صار معلم.\n[C]الاسم: {nickname}\n[C]الرابط: \"\" (أضف الرابط يدويًا في مشرفين.json)", replyTo=mid)
                return

            if txt_str.lower().startswith("tn ahr"):
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
                            
                            save_json(paths["admins"], admins_db)
                            try:
                                sub.demote(userId=uid)
                            except:
                                pass
                            safe_send(sub, chat_id, "✅ تمت إزالة الإشراف، بطلنا منه.", replyTo=mid)
                return

            if txt_str.startswith(("اضف قروب", "إضافة قروب", "اضف_ قروب")):
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

            if txt_str.startswith(("ازالة قروب", "ازل قروب", "إزالة قروب", "إزالة_قروب")):
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
            
            if txt_strip == "ابدا":
                threading.Thread(target=broadcast_message_all, args=("السلام عليكم ورحمة الله وبركاته",), daemon=True).start()
                safe_send(sub, chat_id, "✅ تم إرسال السلام لجميع القروبات.", replyTo=mid)
                return

            if txt_str.startswith("ارسل اعلان:"):
                announcement_text = txt.replace("ارسل اعلان:", "", 1).strip()
                if announcement_text:
                    full_announcement = f"[BC]📢 إعلان المطور:\n{announcement_text}\n⚡️"
                    threading.Thread(target=broadcast_message_all, args=(full_announcement,), daemon=True).start()
                    safe_send(sub, chat_id, "✅ تم إرسال الإعلان لجميع القروبات المراقبة.", replyTo=mid)
                else:
                    safe_send(sub, chat_id, "❌ يرجى إضافة نص الإعلان بعد 'ارسل اعلان:'.", replyTo=mid)
                return
        
        if handle_text_mentioning_dev(txt, sub, chat_id, mid):
            return

        lowered = txt.lower()
        contains_name = any(alias in lowered for alias in BOT_ALIASES)
        
        GREETING_KEYWORDS = [
            "السلام عليكم", "سلام عليكم", "سلام", "مرحبا", "هلا", "صباح الخير", 
            "مساء الخير", "منور", "منوره", "هاي"
        ]
        is_greeting = False
        txt_clean_for_greeting = txt.strip().lower()
        for g in GREETING_KEYWORDS:
            if difflib_ratio(g, txt_clean_for_greeting) > 0.8:
                is_greeting = True
                break

        if mentioned or reply_to_me or contains_name or is_greeting:
            search_text = txt
            
            if contains_name and not (mentioned or reply_to_me or is_greeting):
                for alias in BOT_ALIASES:
                    search_text = re.sub(r'\b' + re.escape(alias) + r'\b', '', search_text, flags=re.IGNORECASE).strip()
            
            resp = search_in_responses(search_text, chatId=chat_id, threshold=0.5)
            
            if not resp:
                if not is_greeting:
                    if GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE" and search_text:
                        resp = call_gemini(search_text)
                    else:
                        resp = get_default_response(chatId=chat_id)
            
            if resp:
                try:
                    sub.send_message(chatId=chatId, message=resp, replyTo=mid)
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
            
            initial_msg = None
            initial_last_mid = None
            
            try:
                initial_msgs = fetch_messages(sub, chat_id, size=1)
                if initial_msgs:
                    initial_msg = initial_msgs[0]
                    initial_last_mid = initial_msg.get("messageId")
            except Exception as e:
                print(f"Failed to fetch initial message for {chat_id}: {e}")

            with message_processing_lock:
                last_message_processed[chat_id] = initial_last_mid
            
            if initial_msg:
                T(target=process_message, args=(initial_msg, sub, chat_obj), daemon=True).start()
            
            while True:
                try:
                    
                    msgs = fetch_messages(sub, chat_id, size=10) 
                    if msgs:
                        msgs.reverse() 
                        
                        new_messages = []
                        with message_processing_lock:
                            last_known_mid = last_message_processed.get(chat_id)

                            if last_known_mid:
                                start_index = -1
                                for i, m in enumerate(msgs):
                                    if m.get("messageId") == last_known_mid:
                                        start_index = i
                                        break
                                
                                new_messages = msgs[start_index + 1:]
                            
                            if new_messages:
                                last_message_processed[chat_id] = new_messages[-1].get("messageId")
                        
                        for m in new_messages:
                            T(target=process_message, args=(m, sub, chat_obj), daemon=True).start()
                    
                    time.sleep(1) 

                except Exception as e:
                    print(f"خطأ داخل حلقة المراقبة للقروب {link}:", e)
                    traceback.print_exc()
                    time.sleep(2)
                    break
        except Exception as e:
            print(f"خطأ عام بمراقبة القروب {link}:", e)
            time.sleep(5)

def main():
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
