import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import glob
import hashlib
import json
import os
import re
from urllib.parse import urljoin
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import pytz
import requests

# ১. সরাসরি গিটহাব সিক্রেটস (GitHub Secrets) থেকে তথ্য রিড করা
FIREBASE_URL = os.environ.get("FIREBASE_URL")
FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET")
AES_KEY_STRING = os.environ.get("AES_KEY")

GITHUB_USER = "bbz36891-stack"
GITHUB_REPO = "Shhwhehighlightshhshsh"
OUTPUT_FILE = "refooty.json"


def get_ist_time():
    """ভারতীয়/বাংলাদেশী সময় জেনারেট করা"""
    tz = pytz.timezone("Asia/Kolkata")
    return datetime.now(tz).strftime("%d/%m/%Y %H:%M:%S IST")


def slugify(text):
    """ইউআরএল ও ফাইল নেম ফ্রেন্ডলি স্ল্যাগ তৈরি করা"""
    if not text:
        return "unknown"
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def extract_teams_from_title(title):
    """টাইটেল থেকে টিম আলাদা করার ফলব্যাক ফাংশন"""
    if not title:
        return None, None
    clean_t = re.sub(
        r"\b(full match|highlights|goals|watch)\b",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()
    parts = re.split(r"\s+(?:vs|v|-|–|—)\s+", clean_t, flags=re.IGNORECASE)
    if len(parts) >= 2:
        t1 = parts[0].strip()
        t2 = parts[1].strip()
        if t1 and t2:
            return t1, t2
    return None, None


def encrypt_payload(data_dict):
    """AES-256-CBC এনক্রিপশন (Web Crypto API & Cloudflare Worker সামঞ্জস্যপূর্ণ)"""
    key = hashlib.sha256(AES_KEY_STRING.encode("utf-8")).digest()
    iv = os.urandom(16)
    json_str = json.dumps(data_dict, ensure_ascii=False)
    padded_bytes = pad(json_str.encode("utf-8"), AES.block_size)

    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted_bytes = cipher.encrypt(padded_bytes)

    # IV এবং Encrypted Data একত্র করে Base64 স্ট্রিং রূপান্তর
    combined = base64.b64encode(iv + encrypted_bytes).decode("utf-8")
    return {"encrypted_data": combined}


def save_encrypted_json(filepath, data_dict):
    """ডাটা এনক্রিপ্ট করে জেসন ফাইলে সেভ করা"""
    encrypted_package = encrypt_payload(data_dict)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(encrypted_package, f, indent=2, ensure_ascii=False)


def main():
    print(f"\n[!] ReFooty AES Encrypted Scraper শুরু: {get_ist_time()}")

    # সিক্রেট ভ্যারিয়েবল চেক করা
    if not FIREBASE_URL or not FIREBASE_SECRET or not AES_KEY_STRING:
        print("[ERROR] প্রয়োজনীয় GitHub Secrets (FIREBASE_URL, FIREBASE_SECRET, AES_KEY) পাওয়া যায়নি!")
        return

    # ১. ফায়ারবেস ডাটাবেজ থেকে ডাটা নামানো
    target_endpoint = f"{FIREBASE_URL.rstrip('/')}/Highlights/matches.json?auth={FIREBASE_SECRET}"
    print("[-] ফায়ারবেস থেকে হাইলাইটস ডাটা সংগৃহীত হচ্ছে...")

    try:
        res = requests.get(target_endpoint, timeout=30)
        res.encoding = "utf-8"

        if res.status_code != 200:
            print(f"[!] ফায়ারবেস থেকে ডাটা পড়তে ব্যর্থ! Status: {res.status_code}")
            return

        raw_data = res.json()
        if not raw_data:
            print("[!] ফায়ারবেসে কোনো ম্যাচ পাওয়া যায়নি!")
            return

        all_matches = list(raw_data.values())
        total_matches = len(all_matches)
        print(f"[+] ফায়ারবেস থেকে মোট {total_matches} টি ম্যাচ পাওয়া গেছে।")

        # ২. পেজ ফাইলসমূহ জেনারেট ও এনক্রিপ্ট করা (page_1.json, page_2.json...)
        print("[-] ১/৩: পেজ ফাইলসমূহ এনক্রিপ্ট করে তৈরি করা হচ্ছে...")
        chunk_size = 100
        page_files_list = []
        total_pages = (total_matches + chunk_size - 1) // chunk_size

        for page_num in range(1, total_pages + 1):
            start_idx = (page_num - 1) * chunk_size
            end_idx = start_idx + chunk_size
            matches_chunk = all_matches[start_idx:end_idx]

            page_filename = f"page_{page_num}.json"
            page_package = {
                "page": page_num,
                "total_pages": total_pages,
                "matches_in_this_page": len(matches_chunk),
                "matches": matches_chunk,
            }

            save_encrypted_json(page_filename, page_package)
            page_files_list.append(page_filename)

        # মেইন refooty.json এনক্রিপ্ট করে সেভ করা
        main_package = {
            "Owner": GITHUB_USER,
            "App_name": "ReFooty AES Encrypted API",
            "Last_update": get_ist_time(),
            "Total_Matches": total_matches,
            "Total_Pages": total_pages,
            "Page_Size": chunk_size,
            "Page_Links": [
                f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/{p}"
                for p in page_files_list
            ],
            "latest_matches": all_matches[:100],
        }
        save_encrypted_json(OUTPUT_FILE, main_package)
        print(f"  [✓] {total_pages} টি পেজ ফাইল এবং {OUTPUT_FILE} এনক্রিপ্টেড সেভ সম্পন্ন।")

        # ৩. কম্পিটিশন/লিগ জেসন ফাইলসমূহ জেনারেট ও এনক্রিপ্ট করা
        print("[-] ২/৩: 'competitions/' ফোল্ডারে এনক্রিপ্টেড লিগ ফাইল তৈরি হচ্ছে...")
        comp_grouped = {}
        for m in all_matches:
            comp_name = m.get("competition", "Other Leagues").strip() or "Other Leagues"
            if comp_name not in comp_grouped:
                comp_grouped[comp_name] = {
                    "cover": m.get("competition_cover", ""),
                    "matches": [],
                }
            comp_grouped[comp_name]["matches"].append(m)

        os.makedirs("competitions", exist_ok=True)
        comp_master_list = []

        for comp_name, comp_info in comp_grouped.items():
            comp_slug = slugify(comp_name)
            filename = f"{comp_slug}.json"
            filepath = os.path.join("competitions", filename)

            comp_data = {
                "competition": comp_name,
                "competition_cover": comp_info["cover"],
                "total_matches": len(comp_info["matches"]),
                "matches": comp_info["matches"],
            }
            save_encrypted_json(filepath, comp_data)

            raw_url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/competitions/{filename}"
            comp_master_list.append({
                "name": comp_name,
                "slug": comp_slug,
                "cover_image": comp_info["cover"],
                "total_matches": len(comp_info["matches"]),
                "json_url": raw_url,
            })

        save_encrypted_json("competitions.json", {
            "Owner": GITHUB_USER,
            "Last_update": get_ist_time(),
            "Total_Competitions": len(comp_master_list),
            "competitions": comp_master_list,
        })
        print(f"  [✓] {len(comp_master_list)} টি লিগের এনক্রিপ্টেড ফাইল তৈরি সম্পন্ন।")

        # ৪. টিম জেসন ফাইলসমূহ জেনারেট ও এনক্রিপ্ট করা
        print("[-] ৩/৩: 'teams/' ফোল্ডারে এনক্রিপ্টেড টিম ফাইল তৈরি হচ্ছে...")
        teams_grouped = {}
        for m in all_matches:
            title = m.get("title", "")
            teams_obj = m.get("teams", {})
            home_obj = teams_obj.get("home_team", {})
            away_obj = teams_obj.get("away_team", {})

            home_name = home_obj.get("name", "").strip()
            away_name = away_obj.get("name", "").strip()
            home_logo = home_obj.get("logo", "")
            away_logo = away_obj.get("logo", "")

            if not home_name or home_name == "Home Team" or not away_name or away_name == "Away Team":
                t1, t2 = extract_teams_from_title(title)
                if t1 and (not home_name or home_name == "Home Team"):
                    home_name = t1
                if t2 and (not away_name or away_name == "Away Team"):
                    away_name = t2

            if home_name and home_name != "Home Team":
                if home_name not in teams_grouped:
                    teams_grouped[home_name] = {"logo": home_logo, "matches": []}
                if m not in teams_grouped[home_name]["matches"]:
                    teams_grouped[home_name]["matches"].append(m)

            if away_name and away_name != "Away Team" and away_name != home_name:
                if away_name not in teams_grouped:
                    teams_grouped[away_name] = {"logo": away_logo, "matches": []}
                if m not in teams_grouped[away_name]["matches"]:
                    teams_grouped[away_name]["matches"].append(m)

        os.makedirs("teams", exist_ok=True)
        team_master_list = []

        for team_name, team_info in teams_grouped.items():
            team_slug = slugify(team_name)
            filename = f"{team_slug}.json"
            filepath = os.path.join("teams", filename)

            team_data = {
                "team": team_name,
                "team_logo": team_info["logo"],
                "total_matches": len(team_info["matches"]),
                "matches": team_info["matches"],
            }
            save_encrypted_json(filepath, team_data)

            raw_url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/teams/{filename}"
            team_master_list.append({
                "name": team_name,
                "slug": team_slug,
                "logo": team_info["logo"],
                "total_matches": len(team_info["matches"]),
                "json_url": raw_url,
            })

        save_encrypted_json("teams.json", {
            "Owner": GITHUB_USER,
            "Last_update": get_ist_time(),
            "Total_Teams": len(team_master_list),
            "teams": team_master_list,
        })
        print(f"  [✓] {len(team_master_list)} টি টিমের এনক্রিপ্টেড ফাইল তৈরি সম্পন্ন।")
        print("\n[SUCCESS] সকল ফাইল সম্পূর্ণ নিরাপদে AES-256 দিয়ে এনক্রিপ্ট হয়ে সেভ হয়েছে!")

    except Exception as e:
        print(f"[ERROR] প্রসেসিং ব্যর্থ: {e}")


if __name__ == "__main__":
    main()
