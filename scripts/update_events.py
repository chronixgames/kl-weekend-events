import os, html, json, re, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

BASE = "https://chronixgames.github.io/kl-weekend-events/"
MYT = timezone(timedelta(hours=8))
NOW = datetime.now(MYT)
TODAY = NOW.date()
HORIZON = TODAY + timedelta(days=45)
MONTHS = ["january","february","march","april","may","june","july","august","september","october","november","december"]

def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0 (compatible; KLWeekendEventsBot/1.0)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()

class EventHeadingParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_heading = False
        self.heading_text = []
        self.heading_link = ""
        self.active = None
        self.items = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("h2", "h3", "h4"):
            if self.active:
                self.items.append(self.active)
            self.active = None
            self.in_heading = True
            self.heading_text = []
            self.heading_link = ""
        elif self.in_heading and tag == "a":
            self.heading_link = attrs.get("href", self.heading_link)
        elif self.active and tag == "a" and not self.active.get("link"):
            href = attrs.get("href", "")
            if href.startswith("http") and "facebook.com" not in href:
                self.active["link"] = href

    def handle_endtag(self, tag):
        if self.in_heading and tag in ("h2", "h3", "h4"):
            title = " ".join(" ".join(self.heading_text).split())
            if title and len(title) > 4 and not any(x in title.lower() for x in ("recent posts","about us","helpful links","public holidays","submit your event","craving more")):
                self.active = {"title": title, "link": self.heading_link, "details": ""}
            self.in_heading = False

    def handle_data(self, data):
        text = " ".join(data.split())
        if not text:
            return
        if self.in_heading:
            self.heading_text.append(text)
        elif self.active and len(self.active["details"]) < 1400:
            self.active["details"] += " " + text

    def finish(self):
        if self.active:
            self.items.append(self.active)
        return self.items

def parse_date(details):
    patterns = [
        r"(\d{1,2}\s+[A-Za-z]+,?\s+20\d{2}[^|]{0,100})",
        r"(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+20\d{2}[^|]{0,100})",
        r"(\d{1,2}\s+[A-Za-z]+\s*-\s*\d{1,2}\s+[A-Za-z]+[^|]{0,60})"
    ]
    for pat in patterns:
        m = re.search(pat, details, re.I)
        if m:
            return " ".join(m.group(1).split())[:160]
    return ""

def category_for(title, details):
    text = (title + " " + details).lower()
    if any(k in text for k in ("kids","kid-friendly","children","child","toddler","family","playdate","meet & greet","halloween","workshop","baking","craft","dinosaur","pokemon","melody")):
        return "가족·키즈"
    if any(k in text for k in ("concert","festival","theatre","theater","music","exhibition","art","market","expo","performance","comedy","nightlife")):
        return "성인·문화"
    return "행사"

def collect_page(url, source_name, limit=80):
    try:
        raw = get(url).decode("utf-8", "replace")
        parser = EventHeadingParser()
        parser.feed(raw)
        rows, seen = [], set()
        for item in parser.finish():
            title = item.get("title","").strip()
            link = item.get("link","").strip()
            details = " ".join(item.get("details","").split())
            if not title or not link.startswith("http") or len(title) < 5:
                continue
            if any(k in title.lower() for k in ("read more","click here","learn more","subscribe","submit your event")):
                continue
            date_text = parse_date(details)
            if not date_text or not re.search(r"20(26|27)", date_text):
                continue
            key = (title.lower(), date_text.lower())
            if key in seen:
                continue
            seen.add(key)
            location = ""
            m = re.search(r"([^|]{3,180})\s*\|\s*\d{1,2}", details)
            if m:
                location = m.group(1).strip(" ·,")
            price = ""
            pm = re.search(r"\bRM\s?\d+(?:\.\d{1,2})?(?:\s*[-–]\s*RM?\s?\d+(?:\.\d{1,2})?)?", details, re.I)
            if pm:
                price = pm.group(0).replace(" ", "")
            rows.append({"title":title,"link":link,"date":date_text,"location":location or "원문에서 장소 확인","price":price or "원문에서 확인","source":source_name,"category":category_for(title,details)})
            if len(rows) >= limit:
                break
        return rows
    except Exception as e:
        print("SOURCE_WARNING:", source_name, type(e).__name__)
        return []

def collect_events():
    urls = [
        (f"https://kualalumpurwithkids.com/whats-on-in-kuala-lumpur-{MONTHS[TODAY.month-1]}/", "Kuala Lumpur with Kids"),
        ("https://discover.calendar2u.com/", "Calendar2U Discover"),
        ("https://www.warisankl.my/events", "Warisan KL"),
        ("https://www.dbkl.gov.my/en", "DBKL Official")
    ]
    all_events, seen = [], set()
    for url, source in urls:
        for item in collect_page(url, source):
            key = (item["title"].lower(), item["date"].lower())
            if key not in seen:
                seen.add(key)
                all_events.append(item)
    return all_events

def holidays():
    url = f"https://date.nager.at/api/v3/PublicHolidays/{TODAY.year}/MY"
    out = []
    try:
        data = json.loads(get(url))
        out = [x for x in data if TODAY.isoformat() <= x.get("date","") <= HORIZON.isoformat()]
    except Exception:
        pass
    if TODAY <= datetime(2026,10,26).date() <= HORIZON:
        out.append({"date":"2026-10-26","localName":"셀랑고르 주 공휴일 대체휴일 (술탄 즉위 25주년 기념)","name":"Selangor state public holiday (replacement day)"})
    return sorted(out, key=lambda x: x.get("date",""))

def card(item):
    title = html.escape(item.get("title",""))
    link = html.escape(item.get("link","#"), quote=True)
    date = html.escape(item.get("date","일정 원문 확인"))
    location = html.escape(item.get("location","원문에서 장소 확인"))
    price = html.escape(item.get("price","원문에서 확인"))
    source = html.escape(item.get("source",""))
    category = html.escape(item.get("category","행사"))
    return f'<article class="event"><div class="top"><span class="pill">{category}</span><span class="source">{source}</span></div><h3><a href="{link}" target="_blank" rel="noopener">{title}</a></h3><p class="meta"><b>📅 일정</b> {date}</p><p class="meta"><b>📍 장소</b> {location}</p><p class="meta"><b>🎟️ 가격</b> {price}</p><p><a class="detail" href="{link}" target="_blank" rel="noopener">공식/원문에서 상세 정보 확인 ↗</a></p></article>'

def holiday_card(item):
    name = html.escape(item.get("localName") or item.get("name") or "공휴일")
    date = html.escape(item.get("date",""))
    en = html.escape(item.get("name",""))
    return f'<article class="event"><span class="pill">공휴일</span><h3>{name}</h3><p class="meta">{date} · {en}</p></article>'

def build_page(events, hols):
    # Only replace the live detailed page when the scraper found a dated event this weekend.
    weekend_start = TODAY + timedelta(days=(5 - TODAY.weekday()) % 7)
    weekend_end = weekend_start + timedelta(days=1)
    this_weekend = []
    for item in events:
        date_text = item.get("date", "")
        parsed = re.findall(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(20\d{2})", date_text, re.I)
        for day, month_name, year in parsed:
            try:
                event_day = datetime.strptime(f"{day} {month_name} {year}", "%d %B %Y").date()
                if weekend_start <= event_day <= weekend_end:
                    this_weekend.append(item)
                    break
            except ValueError:
                continue
    if not this_weekend:
        print("PAGE_NOT_OVERWRITTEN: no reliably dated event found for the upcoming weekend")
        return
    family = [x for x in events if x["category"] == "가족·키즈"]
    adult = [x for x in events if x["category"] != "가족·키즈"]
    stamp = NOW.strftime("%Y-%m-%d %H:%M MYT")
    def section(title, items):
        body = "".join(card(x) for x in items) or '<p class="muted">현재 일정과 날짜를 함께 확인할 수 있는 항목이 없습니다. 아래 행사 캘린더에서 추가 정보를 확인해 주세요.</p>'
        return f'<section><h2>{title}</h2>{body}</section>'
    content = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KL & Selangor Weekend Events</title><meta name="description" content="쿠알라룸푸르와 셀랑고르의 최신 주말 행사, 가족·키즈 활동, 성인 문화 행사와 공휴일을 확인하세요.">
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f3f6fb;color:#172033;font-family:Arial,'Noto Sans KR',sans-serif;line-height:1.6}}header{{background:linear-gradient(135deg,#172554,#334e9b);color:#fff;padding:28px 17px}}header div,main,footer{{max-width:880px;margin:auto}}h1{{margin:0;font-size:clamp(25px,6vw,36px);line-height:1.2}}header p{{color:#dbeafe;margin:9px 0 0}}main{{padding:16px 12px 38px}}.notice{{background:#fff;border:1px solid #dfe5ef;border-radius:13px;padding:14px;margin:0 0 22px}}section{{margin:0 0 26px}}h2{{font-size:21px;margin:0 0 10px}}.event{{background:#fff;border:1px solid #dfe5ef;border-radius:13px;padding:15px;margin:10px 0;box-shadow:0 2px 7px #1b2b4a0b}}h3{{font-size:17px;line-height:1.4;margin:9px 0}}.meta,.muted{{color:#536078;font-size:14px;margin:5px 0;overflow-wrap:anywhere}}a{{color:#2457b5;overflow-wrap:anywhere}}.top{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}.pill{{display:inline-block;background:#e8efff;color:#253f8c;padding:3px 9px;border-radius:18px;font-size:12px;font-weight:700}}.source{{font-size:12px;color:#6b7280}}.detail{{display:inline-block;margin-top:5px;font-weight:700;text-decoration:none}}footer{{padding:0 14px 30px;color:#687386;font-size:12px}}
</style></head><body><header><div><h1>KL & Selangor Weekend Events</h1><p>주말에 갈 만한 행사만 모아보기 · 가족·키즈 · 성인·문화 · 공휴일</p></div></header><main>
<div class="notice"><b>마지막 업데이트:</b> {stamp}<p class="muted">날짜·장소·가격은 원문에서 추출한 정보입니다. 일정 변경 가능성이 있으니 방문 전 상세 링크에서 주최 측 공지를 확인해 주세요. 확인되지 않은 정보는 ‘원문 확인’으로 표시합니다.</p><p><a href="https://kualalumpurwithkids.com/events/month/" target="_blank" rel="noopener">가족 행사 캘린더</a> · <a href="https://discover.calendar2u.com/" target="_blank" rel="noopener">전체 행사 캘린더</a> · <a href="https://www.warisankl.my/events" target="_blank" rel="noopener">Warisan KL 문화 행사</a> · <a href="https://www.dbkl.gov.my/en" target="_blank" rel="noopener">쿠알라룸푸르 시청 행사</a></p></div>
{section("📌 다가오는 주말 추천", this_weekend[:12])}
{section("👨‍👩‍👧‍👦 가족·키즈 행사", family[:20])}
{section("🎭 성인·문화·전시·마켓", adult[:20])}
<section><h2>🇲🇾 다가오는 말레이시아 공휴일</h2>{''.join(holiday_card(x) for x in hols) or '<p class="muted">향후 45일 내 전국 공휴일이 없거나 공휴일 정보를 가져오지 못했습니다. 주별 공휴일은 별도로 확인해 주세요.</p>'}</section>
</main><footer>KL & Selangor Weekend Events · 외부 공개 행사 캘린더를 모아 보여주는 안내 페이지입니다. 행사 개최 및 입장 조건은 주최 측 공식 안내를 기준으로 확인해 주세요.</footer></body></html>"""
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html","w",encoding="utf-8") as f:
        f.write(content)

def upcoming_weekend_events(events):
    weekend_start = TODAY + timedelta(days=(5 - TODAY.weekday()) % 7)
    weekend_end = weekend_start + timedelta(days=1)
    selected, seen = [], set()
    for item in events:
        date_text = item.get("date", "")
        parsed = re.findall(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(20\d{2})", date_text, re.I)
        for day, month_name, year in parsed:
            try:
                event_day = datetime.strptime(f"{day} {month_name} {year}", "%d %B %Y").date()
                if weekend_start <= event_day <= weekend_end:
                    key = (item.get("title", "").lower(), date_text.lower())
                    if key not in seen:
                        seen.add(key)
                        selected.append(item)
                    break
            except ValueError:
                continue
    return selected

def kakao_send(events, hols):
    rest = os.environ["KAKAO_REST_API_KEY"]
    access = os.environ.get("KAKAO_ACCESS_TOKEN", "")
    refresh = os.environ.get("KAKAO_REFRESH_TOKEN", "")
    secret = os.environ.get("KAKAO_CLIENT_SECRET", "")
    weekend = upcoming_weekend_events(events)
    weekend_label = f"{(TODAY + timedelta(days=(5 - TODAY.weekday()) % 7)).strftime('%m/%d')}–{(TODAY + timedelta(days=(5 - TODAY.weekday()) % 7) + timedelta(days=1)).strftime('%m/%d')}"
    lines = [f"🇲🇾 KL·셀랑고르 주말 행사 ({weekend_label})"]
    if weekend:
        for item in weekend[:3]:
            title = item.get("title", "행사")
            date = item.get("date", "날짜 원문 확인")
            place = item.get("location", "장소 원문 확인")
            price = item.get("price", "가격 원문 확인")
            lines.append(f"• {title} | {date} | {place} | {price}")
        if len(weekend) > 3:
            lines.append(f"외 {len(weekend)-3}개 행사")
    else:
        lines.append("이번 주말 날짜를 신뢰성 있게 확인한 행사 정보를 찾지 못했습니다.")
        lines.append("아래 페이지에서 행사 캘린더와 최신 안내를 확인해 주세요.")
    if hols:
        next_holiday = hols[0]
        lines.append(f"🇲🇾 공휴일: {next_holiday.get('date','')} {next_holiday.get('localName') or next_holiday.get('name','')}")
    lines.append("상세 행사 페이지: " + BASE)
    text_body = "\n".join(lines)
    message = {
        "object_type": "text",
        "text": text_body[:1900],
        "link": {"web_url": BASE, "mobile_web_url": BASE},
        "button_title": "주말 행사 상세 보기"
    }
    def send(token):
        payload = urllib.parse.urlencode({"template_object": json.dumps(message, ensure_ascii=False)}).encode()
        req = urllib.request.Request(
            "https://kapi.kakao.com/v2/api/talk/memo/default/send",
            data=payload,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode()
        except urllib.error.HTTPError as e:
            return "HTTP_ERROR:" + str(e.code) + ":" + e.read().decode()
    result = send(access) if access else "NO_ACCESS_TOKEN"
    if result.startswith("HTTP_ERROR:401") and refresh:
        form = {"grant_type": "refresh_token", "client_id": rest, "refresh_token": refresh}
        if secret:
            form["client_secret"] = secret
        req = urllib.request.Request(
            "https://kauth.kakao.com/oauth/token",
            data=urllib.parse.urlencode(form).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                token_data = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            # Log Kakao's diagnostic response, but never log credentials or tokens.
            error_body = e.read().decode("utf-8", "replace")
            raise RuntimeError(
                f"Kakao token refresh failed (HTTP {e.code}). "
                f"Kakao response: {error_body[:800]}"
            ) from None
        access = token_data["access_token"]
        result = send(access)
        print("KAKAO_ACCESS_TOKEN_REFRESHED")
        if token_data.get("refresh_token"):
            print("A_REFRESH_TOKEN_WAS_ROTATED")
    if not result.startswith("{") or '"result_code":0' not in result:
        raise RuntimeError("Kakao message send failed. Check token/secrets. Response: " + result[:400])
    print(f"KAKAO_MESSAGE_SENT: {len(weekend)} dated events for the upcoming weekend")

def main():
    events = collect_events()
    hols = holidays()
    build_page(events, hols)
    print(f"Page updated: {len(events)} dated event leads, {len(hols)} public holidays")
    kakao_send(events, hols)

if __name__ == "__main__":
    main()
