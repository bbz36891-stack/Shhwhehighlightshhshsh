from datetime import datetime
import json
import os
import re
from urllib.parse import urljoin
import pytz
import requests

# ১. ফায়ারবেস কনফিগারেশন
FIREBASE_URL = "https://fusion-sports-2c3d2-default-rtdb.firebaseio.com/"
FIREBASE_SECRET = "uogZkbCFyw8CHBurNCZWUeakOOshWKbHf2XlxWKR"

# ২. গিটহাব কনফিগারেশন
GITHUB_USER = "bbz36891-stack"
GITHUB_REPO = "Shhwhehighlightshhshsh"
GITHUB_EMAIL = "bbz36891@gmail.com"
GITHUB_TOKEN = "YOUR_GITHUB_PAT_TOKEN"  # <--- আপনার গিটহাব PAT টোকেনটি এখানে বসাবেন

OUTPUT_FILE = "refooty.json"


def get_ist_time():
    """ভারতীয়/বাংলাদেশী বর্তমান সময় বের করা"""
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


def push_everything_to_github():
    """তৈরি হওয়া সকল ফাইল এক ক্লিকে গিটহাবে পুশ করার লজিক"""
    print("\n[-] গিটহাবে সকল ফাইল পুশ করা হচ্ছে...")
    remote_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_USER}/{GITHUB_REPO}.git"

    try:
        os.system(f'git config --global user.email "{GITHUB_EMAIL}"')
        os.system(f'git config --global user.name "{GITHUB_USER}"')
        os.system(f"git remote set-url origin {remote_url}")

        # সকল জেসন ফাইল ও ফোল্ডার গিটহাবে ট্র্যাক করা
        os.system("git add .")
        os.system(
            f'git commit -m "Auto DB Sync All Files: {get_ist_time()}"'
        )
        os.system("git push origin main")

        print(
            "\n[SUCCESS] ১০০% সফলতা! ফায়ারবেসের সকল ডাটা গিটহাবে আপলোড হয়ে গেছে!"
        )
    except Exception as e:
        print(f"[ERROR] গিটহাব পুশ করতে ব্যর্থ: {e}")


def main_sync():
    print(
        f"=========================================="
    )
    print(
        f"  ReFooty DB Sync Scraper Started: {get_ist_time()}"
    )
    print(
        f"=========================================="
    )

    # ১. ফায়ারবেস ডাটাবেজের 'Highlights/matches' নোড থেকে ডাটা রিড করা
    print("\n[-] ফায়ারবেস 'Highlights/matches' থেকে ডাটা নামানো হচ্ছে...")
    target_endpoint = (
        f"{FIREBASE_URL.rstrip('/')}/Highlights/matches.json?auth={FIREBASE_SECRET}"
    )

    try:
        res = requests.get(target_endpoint, timeout=30)
        res.encoding = "utf-8"

        if res.status_code != 200:
            print(
                f"[!] ফায়ারবেস থেকে ডাটা রিড করতে ব্যর্থ! Status Code: {res.status_code}"
            )
            return

        raw_db_data = res.json()
        if not raw_db_data:
            print("[!] ডাটাবেজে কোনো হাইলাইটস ম্যাচ পাওয়া যায়নি!")
            return

        all_matches = list(raw_db_data.values())
        total_matches = len(all_matches)
        print(
            f"[+] ডাটাবেজ থেকে সফলভাবে {total_matches} টি ম্যাচ রিড করা হয়েছে।"
        )

        # ২. পেজ সিস্টেম ফাইল তৈরি করা (১০০টি করে ম্যাচ ধরে)
        print("\n[-] ১/৪: পেজ ফাইলসমূহ (page_1.json, page_2.json...) তৈরি হচ্ছে...")
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

            with open(page_filename, "w", encoding="utf-8") as pf:
                json.dump(page_package, pf, indent=4, ensure_ascii=False)

            page_files_list.append(page_filename)

        # মেইন refooty.json সেভ করা
        main_package = {
            "Owner": GITHUB_USER,
            "Telegram": "https://t.me/iVan_flux",
            "App_name": "ReFooty DB Sync Master API",
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

        with open(OUTPUT_FILE, "w", encoding="utf-8") as mf:
            json.dump(main_package, mf, indent=4, ensure_ascii=False)

        print(f"  [✓] {total_pages} টি পেজ ফাইল এবং {OUTPUT_FILE} তৈরি সম্পন্ন।")

        # ৩. কম্পিটিশন/লিগ অনুযায়ী পৃথক জেসন তৈরি
        print("\n[-] ২/৪: 'competitions/' ফোল্ডারে লিগ ফাইল জেনারেট হচ্ছে...")
        comp_grouped = {}
        for m in all_matches:
            comp_name = m.get("competition", "Other Leagues").strip()
            if not comp_name:
                comp_name = "Other Leagues"

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

            with open(filepath, "w", encoding="utf-8") as cf:
                json.dump(comp_data, cf, indent=4, ensure_ascii=False)

            raw_url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/competitions/{filename}"
            comp_master_list.append(
                {
                    "name": comp_name,
                    "slug": comp_slug,
                    "cover_image": comp_info["cover"],
                    "total_matches": len(comp_info["matches"]),
                    "json_url": raw_url,
                }
            )

        with open("competitions.json", "w", encoding="utf-8") as cmf:
            json.dump(
                {
                    "Owner": GITHUB_USER,
                    "Last_update": get_ist_time(),
                    "Total_Competitions": len(comp_master_list),
                    "competitions": comp_master_list,
                },
                cmf,
                indent=4,
                ensure_ascii=False,
            )

        print(f"  [✓] {len(comp_master_list)} টি লিগের পৃথক ফাইল তৈরি সম্পন্ন।")

        # ৪. টিম অনুযায়ী পৃথক জেসন তৈরি (Zero-Skip Logic)
        print("\n[-] ৩/৪: 'teams/' ফোল্ডারে প্রতিটি দলের আলাদা ফাইল জেনারেট হচ্ছে...")
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

            # টাইটেল থেকে টিম বের করা
            if (
                not home_name
                or home_name == "Home Team"
                or not away_name
                or away_name == "Away Team"
            ):
                t1, t2 = extract_teams_from_title(title)
                if t1 and (not home_name or home_name == "Home Team"):
                    home_name = t1
                if t2 and (not away_name or away_name == "Away Team"):
                    away_name = t2

            if home_name and home_name != "Home Team":
                if home_name not in teams_grouped:
                    teams_grouped[home_name] = {
                        "logo": home_logo,
                        "matches": [],
                    }
                if m not in teams_grouped[home_name]["matches"]:
                    teams_grouped[home_name]["matches"].append(m)

            if (
                away_name
                and away_name != "Away Team"
                and away_name != home_name
            ):
                if away_name not in teams_grouped:
                    teams_grouped[away_name] = {
                        "logo": away_logo,
                        "matches": [],
                    }
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

            with open(filepath, "w", encoding="utf-8") as tf:
                json.dump(team_data, tf, indent=4, ensure_ascii=False)

            raw_url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/teams/{filename}"
            team_master_list.append(
                {
                    "name": team_name,
                    "slug": team_slug,
                    "logo": team_info["logo"],
                    "total_matches": len(team_info["matches"]),
                    "json_url": raw_url,
                }
            )

        with open("teams.json", "w", encoding="utf-8") as tmf:
            json.dump(
                {
                    "Owner": GITHUB_USER,
                    "Last_update": get_ist_time(),
                    "Total_Teams": len(team_master_list),
                    "teams": team_master_list,
                },
                tmf,
                indent=4,
                ensure_ascii=False,
            )

        print(f"  [✓] {len(team_master_list)} টি দলের পৃথক ফাইল তৈরি সম্পন্ন।")

        # ৫. গিটহাবে অটো-পুশ করা
        print("\n[-] ৪/৪: গিটহাবে ফাইলসমূহ আপলোড হচ্ছে...")
        push_everything_to_github()

    except Exception as e:
        print(f"\n[ERROR] প্রসেসিং করার সময় এরর: {e}")


if __name__ == "__main__":
    main_sync()
