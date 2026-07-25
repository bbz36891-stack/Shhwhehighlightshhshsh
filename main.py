import base64
from datetime import datetime
import hashlib
import json
import os
import re
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import pytz
import requests

FIREBASE_URL = os.environ.get("FIREBASE_URL")
FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET")
AES_KEY_STRING = os.environ.get("AES_KEY")

GITHUB_USER = "bbz36891-stack"
GITHUB_REPO = "Shhwhehighlightshhshsh"
OUTPUT_FILE = "refooty.json"


def get_ist_time():
    tz = pytz.timezone("Asia/Kolkata")
    return datetime.now(tz).strftime("%I:%M:%S %p %d-%m-%Y")


def slugify(text):
    if not text:
        return "unknown"
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def extract_teams_from_title(title):
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


def format_match_object(m):
    title = m.get("title", "Football Match")
    thumbnail_url = m.get("thumbnail_url", "")
    competition = m.get("competition", "Unknown Competition")
    competition_cover = m.get("competition_cover", "")
    match_date = m.get("date", "")

    teams_obj = m.get("teams", {})
    home_obj = teams_obj.get("home_team", {})
    away_obj = teams_obj.get("away_team", {})

    events_info = {
        "away_team": {
            "logo": away_obj.get("logo", ""),
            "name": away_obj.get("name", "Away Team"),
            "score": away_obj.get("score", "0"),
        },
        "home_team": {
            "logo": home_obj.get("logo", ""),
            "name": home_obj.get("name", "Home Team"),
            "score": home_obj.get("score", "0"),
        },
        "status": teams_obj.get("status", "FT"),
    }

    streams = m.get("streams", [])
    events_timeline = m.get("events_timeline", [])
    head_to_head = m.get("head_to_head", {})
    statistics = m.get("statistics", {})
    description = m.get("description", "")

    return {
        "title": title,
        "thumbnail_url": thumbnail_url,
        "competition": competition,
        "competition_cover": competition_cover,
        "date": match_date,
        "events_info": events_info,
        "streams": streams,
        "events_timeline": events_timeline,
        "head_to_head": head_to_head,
        "statistics": statistics,
        "description": description,
    }


def encrypt_payload(data_dict):
    key = hashlib.sha256(AES_KEY_STRING.encode("utf-8")).digest()
    iv = os.urandom(16)
    json_str = json.dumps(data_dict, ensure_ascii=False)
    padded_bytes = pad(json_str.encode("utf-8"), AES.block_size)

    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted_bytes = cipher.encrypt(padded_bytes)

    combined = base64.b64encode(iv + encrypted_bytes).decode("utf-8")
    return {"encrypted_data": combined}


def save_encrypted_json(filepath, data_dict):
    encrypted_package = encrypt_payload(data_dict)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(encrypted_package, f, indent=2, ensure_ascii=False)


def build_trademark_package(matches_chunk, total_count, page_num, total_pages):
    package = {
        " NAME ": "Highlights by flux ( Auto updated)",
        "AUTHOR": "iVan_FluX",
        "CONTACT (OWNER)": "https://t.me/iVan_flux",
        "TELEGRAM CHANNEL": "https://t.me/api_hub_by_ivan",
        "Last update time": get_ist_time(),
        "matches": matches_chunk,
    }

    if total_count >= 25:
        package["hasMore"] = page_num < total_pages
        package["currentCount"] = len(matches_chunk)
        package["totalCount"] = total_count
        package["currentPage"] = page_num
        package["lastPage"] = total_pages

    return package


def build_competition_package(comp_name, comp_cover, matches_chunk, total_count, page_num, total_pages):
    package = {
        "competition": comp_name,
        "competition_cover": comp_cover,
        "total_matches": total_count,
        "matches": matches_chunk,
    }

    if total_count >= 25:
        package["hasMore"] = page_num < total_pages
        package["currentCount"] = len(matches_chunk)
        package["totalCount"] = total_count
        package["currentPage"] = page_num
        package["lastPage"] = total_pages

    return package


def build_team_package(team_name, team_logo, matches_chunk, total_count, page_num, total_pages):
    package = {
        "team": team_name,
        "team_logo": team_logo,
        "total_matches": total_count,
        "matches": matches_chunk,
    }

    if total_count >= 25:
        package["hasMore"] = page_num < total_pages
        package["currentCount"] = len(matches_chunk)
        package["totalCount"] = total_count
        package["currentPage"] = page_num
        package["lastPage"] = total_pages

    return package


def main():
    if not FIREBASE_URL or not FIREBASE_SECRET or not AES_KEY_STRING:
        return

    target_endpoint = f"{FIREBASE_URL.rstrip('/')}/Highlights/matches.json?auth={FIREBASE_SECRET}"

    try:
        res = requests.get(target_endpoint, timeout=30)
        res.encoding = "utf-8"

        if res.status_code != 200:
            return

        raw_data = res.json()
        if not raw_data:
            return

        raw_matches_list = list(raw_data.values())
        formatted_matches = [format_match_object(m) for m in raw_matches_list]
        total_matches = len(formatted_matches)

        chunk_size = 25
        total_pages = (total_matches + chunk_size - 1) // chunk_size

        for page_num in range(1, total_pages + 1):
            start_idx = (page_num - 1) * chunk_size
            end_idx = start_idx + chunk_size
            matches_chunk = formatted_matches[start_idx:end_idx]

            page_filename = f"page_{page_num}.json"
            page_package = build_trademark_package(
                matches_chunk, total_matches, page_num, total_pages
            )
            save_encrypted_json(page_filename, page_package)

            if page_num == 1:
                save_encrypted_json(OUTPUT_FILE, page_package)

        comp_grouped = {}
        for m in formatted_matches:
            comp_name = (
                m.get("competition", "Other Leagues").strip() or "Other Leagues"
            )
            comp_slug = slugify(comp_name)

            if comp_slug not in comp_grouped:
                comp_grouped[comp_slug] = {
                    "name": comp_name,
                    "cover": m.get("competition_cover", ""),
                    "matches": [],
                }

            if m not in comp_grouped[comp_slug]["matches"]:
                comp_grouped[comp_slug]["matches"].append(m)

        os.makedirs("competitions", exist_ok=True)
        comp_master_list = []

        for comp_slug, comp_info in comp_grouped.items():
            comp_matches = comp_info["matches"]
            comp_total = len(comp_matches)
            comp_pages = (comp_total + chunk_size - 1) // chunk_size

            for p_num in range(1, comp_pages + 1):
                s_idx = (p_num - 1) * chunk_size
                e_idx = s_idx + chunk_size
                c_chunk = comp_matches[s_idx:e_idx]

                if p_num == 1:
                    filepath = os.path.join("competitions", f"{comp_slug}.json")
                else:
                    filepath = os.path.join(
                        "competitions", f"{comp_slug}_page_{p_num}.json"
                    )

                c_pkg = build_competition_package(
                    comp_info["name"],
                    comp_info["cover"],
                    c_chunk,
                    comp_total,
                    p_num,
                    comp_pages,
                )
                save_encrypted_json(filepath, c_pkg)

            raw_url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/competitions/{comp_slug}.json"
            comp_master_list.append({
                "name": comp_info["name"],
                "slug": comp_slug,
                "cover_image": comp_info["cover"],
                "total_matches": comp_total,
                "json_url": raw_url,
            })

        save_encrypted_json(
            "competitions.json",
            {
                "Total_Competitions": len(comp_master_list),
                "competitions": comp_master_list,
            },
        )

        teams_grouped = {}
        for m in formatted_matches:
            title = m.get("title", "")
            events_info = m.get("events_info", {})
            home_obj = events_info.get("home_team", {})
            away_obj = events_info.get("away_team", {})

            home_name = home_obj.get("name", "").strip()
            away_name = away_obj.get("name", "").strip()
            home_logo = home_obj.get("logo", "")
            away_logo = away_obj.get("logo", "")

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
                h_slug = slugify(home_name)
                if h_slug not in teams_grouped:
                    teams_grouped[h_slug] = {
                        "name": home_name.title(),
                        "logo": home_logo,
                        "matches": [],
                    }
                elif not teams_grouped[h_slug]["logo"] and home_logo:
                    teams_grouped[h_slug]["logo"] = home_logo

                if m not in teams_grouped[h_slug]["matches"]:
                    teams_grouped[h_slug]["matches"].append(m)

            if (
                away_name
                and away_name != "Away Team"
                and away_name != home_name
            ):
                a_slug = slugify(away_name)
                if a_slug not in teams_grouped:
                    teams_grouped[a_slug] = {
                        "name": away_name.title(),
                        "logo": away_logo,
                        "matches": [],
                    }
                elif not teams_grouped[a_slug]["logo"] and away_logo:
                    teams_grouped[a_slug]["logo"] = away_logo

                if m not in teams_grouped[a_slug]["matches"]:
                    teams_grouped[a_slug]["matches"].append(m)

        os.makedirs("teams", exist_ok=True)
        team_master_list = []

        for team_slug, team_info in teams_grouped.items():
            t_matches = team_info["matches"]
            t_total = len(t_matches)
            t_pages = (t_total + chunk_size - 1) // chunk_size

            for p_num in range(1, t_pages + 1):
                s_idx = (p_num - 1) * chunk_size
                e_idx = s_idx + chunk_size
                t_chunk = t_matches[s_idx:e_idx]

                if p_num == 1:
                    filepath = os.path.join("teams", f"{team_slug}.json")
                else:
                    filepath = os.path.join(
                        "teams", f"{team_slug}_page_{p_num}.json"
                    )

                t_pkg = build_team_package(
                    team_info["name"],
                    team_info["logo"],
                    t_chunk,
                    t_total,
                    p_num,
                    t_pages,
                )
                save_encrypted_json(filepath, t_pkg)

            raw_url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/teams/{team_slug}.json"
            team_master_list.append({
                "name": team_info["name"],
                "slug": team_slug,
                "logo": team_info["logo"],
                "total_matches": t_total,
                "json_url": raw_url,
            })

        save_encrypted_json(
            "teams.json",
            {
                "Total_Teams": len(team_master_list),
                "teams": team_master_list,
            },
        )

    except Exception:
        pass


if __name__ == "__main__":
    main()
