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

def verified_weekend_fallbacks():
    """Small, dated fallback list for Oct 31–Nov 1, 2026 when source parsing misses cards."""
    weekend_start = TODAY + timedelta(days=(5 - TODAY.weekday()) % 7)
    if weekend_start != datetime(2026, 10, 31).date():
        return []
    return [
        {"title":"Kiddie CEO Halloween Takeover","link":"https://kualalumpurwithkids.com/whats-on-in-kuala-lumpur-october/","date":"31 October 2026 - 1 November 2026","location":"The Campus Ampang, Selangor","price":"원문에서 확인","source":"KL With Kids","category":"가족·키즈"},
        {"title":"Halloween Science and Maker Experience in Bangsar","link":"https://kualalumpurwithkids.com/whats-on-in-kuala-lumpur-october/","date":"31 October 2026 - 1 November 2026","location":"Bangsar, Kuala Lumpur","price":"RM99","source":"KL With Kids","category":"가족·키즈"},
        {"title":"Treats & Sweets All Day at The Campus Ampang","link":"https://kualalumpurwithkids.com/whats-on-in-kuala-lumpur-october/","date":"31 October 2026 - 1 November 2026","location":"The Campus Ampang, Selangor","price":"원문에서 확인","source":"KL With Kids","category":"가족·키즈"},
        {"title":"Boo! @ GMBB Halloween Weekend","link":"https://whatsonkl.com/events-preview/2026-10-31/","date":"31 October 2026 - 1 November 2026","location":"GMBB KL, Jalan Robertson, Kuala Lumpur","price":"무료 입장","source":"What's on KL?","category":"성인·문화"},
        {"title":"KLove Market","link":"https://whatsonkl.com/events-preview/2026-10-31/","date":"31 October 2026 - 1 November 2026","location":"KLOE Hotel, 227 Jalan Bukit Bintang, Kuala Lumpur","price":"무료 입장","source":"What's on KL?","category":"성인·문화"},
        {"title":"GeekCon Halloween Edition","link":"https://geekconasia.com/","date":"30 October 2026 - 1 November 2026","location":"MITEC, Kuala Lumpur","price":"RM15부터 (일반 입장)","source":"GeekCon Asia 공식","category":"가족·키즈"}
    ]

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
    for item in verified_weekend_fallbacks():
        key = (item["title"].lower(), item["date"].lower())
        if key not in seen:
            seen.add(key)
            all_events.append(item)
    print(f"VERIFIED_WEEKEND_FALLBACKS: {len(verified_weekend_fallbacks())}")
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

EVENT_KO_TITLES = {
    "Meet and Greet Sanrio Chararters at Sunway Pyramid": "선리오 캐릭터와 만나는 행사",
    "Kiddie CEO Halloween Takeover": "키디 CEO 할로윈 체험 행사",
    "Kiddie CEO Halloween Takeover at The Campus Ampang": "캠퍼스 암팡 키디 CEO 할로윈 행사",
    "Halloween sensory-friendly fun activities at Campus Ampang": "캠퍼스 암팡 감각 친화형 할로윈 체험",
    "Nature Guided Walk at Taman Tugu": "타만 투구 자연 가이드 산책",
    "Forest Bathing at Taman Tugu": "타만 투구 숲속 힐링 체험",
    "3D Printing Workshop at Hartamas Shopping Centre": "하르타마스 쇼핑센터 3D 프린팅 워크숍",
    "Halloween Science and Maker Experience in Bangsar": "방사르 할로윈 과학·메이커 체험",
    "Treats & Sweets All Day at The Campus Ampang": "캠퍼스 암팡 간식·디저트 행사",
    "Boo! @ GMBB Halloween Weekend": "GMBB 할로윈 주말 행사 ‘부!’",
    "KLove Market": "클로브 마켓",
    "GeekCon Halloween Edition": "긱콘 할로윈 에디션",
}
def korean_title(title):
    return EVENT_KO_TITLES.get(title, title)

KOREAN_MONTHS = {
    "January":"1월", "February":"2월", "March":"3월", "April":"4월",
    "May":"5월", "June":"6월", "July":"7월", "August":"8월",
    "September":"9월", "October":"10월", "November":"11월", "December":"12월",
}
def korean_date(value):
    # Convert English and ISO dates to Korean month/day with weekday; omit year.
    def render_day(day, month_name, year):
        parsed = datetime.strptime(f"{int(day)} {month_name} {int(year)}", "%d %B %Y")
        weekday = ["월", "화", "수", "목", "금", "토", "일"][parsed.weekday()]
        return f"{parsed.month}월 {parsed.day}일({weekday})"
    def replace_date(m):
        try:
            return render_day(m.group(1), m.group(2), m.group(3))
        except ValueError:
            return m.group(0)
    value = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(20\d{2})\b", replace_date, value, flags=re.I)
    def replace_date2(m):
        try:
            return render_day(m.group(2), m.group(1), m.group(3))
        except ValueError:
            return m.group(0)
    value = re.sub(r"\b([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(20\d{2})\b", replace_date2, value, flags=re.I)
    def replace_iso(m):
        try:
            d = datetime.strptime(m.group(0), "%Y-%m-%d")
            weekday = ["월", "화", "수", "목", "금", "토", "일"][d.weekday()]
            return f"{d.month}월 {d.day}일({weekday})"
        except ValueError:
            return m.group(0)
    value = re.sub(r"\b20\d{2}-\d{2}-\d{2}\b", replace_iso, value)
    value = re.sub(r"\b20\d{2}\b", "", value)
    for en, ko in KOREAN_MONTHS.items():
        value = re.sub(rf"\b{en}\b", ko, value, flags=re.I)
    value = re.sub(r"\s{2,}", " ", value)
    return value.strip(" ,·")

def korean_date_html(value):
    escaped = html.escape(korean_date(value))
    escaped = re.sub(r"(\(토\))", r'<span class="date-sat">\1</span>', escaped)
    escaped = re.sub(r"(\(일\))", r'<span class="date-sun">\1</span>', escaped)
    return escaped

def is_instagram_event(item):
    source = (item.get("source", "") + " " + item.get("link", "")).lower()
    category = item.get("category", "")
    return category == "인스타그램" or "instagram.com" in source or "인스타그램" in source

def clean_event_date(value):
    # Remove times and prices that were accidentally included in the source date text.
    value = re.sub(r"\b\d{1,2}:\d{2}\s*(?:AM|PM)\b", "", value, flags=re.I)
    value = re.sub(r"\bRM\s?\d+(?:\.\d{1,2})?\b", "", value, flags=re.I)
    value = re.sub(r"\s{2,}", " ", value)
    return value.strip(" ·,-")

def simplify_location(location):
    """Show only a recognizable area/venue name, not a full street address."""
    raw = re.sub(r"[,\s]*Malaysia\b", "", location or "", flags=re.I).strip(" ,·-")
    low = raw.lower()
    rules = [
        (("the campus ampang", "ampang"), "암팡"),
        (("sunway pyramid", "bandar sunway"), "반다르 선웨이"),
        (("gmbb", "jalan robertson"), "쿠알라룸푸르 시내(GMBB)"),
        (("kloe hotel", "jalan bukit bintang"), "부킷 빈탕"),
        (("mitec",), "쿠알라룸푸르(MITEC)"),
        (("bangsar",), "방사르"),
        (("taman tugu",), "타만 투구"),
        (("hartamas",), "스리 하르타마스"),
    ]
    for keys, label in rules:
        if any(key in low for key in keys):
            return label
    # Fall back to the first meaningful venue/area segment, stripping postcode/street detail.
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return "장소 원문 확인"
    first = parts[0]
    first = re.sub(r"\b\d{4,6}\b", "", first).strip()
    return first[:70] or "장소 원문 확인"

def event_intro(item):
    text = (item.get("title", "") + " " + item.get("category", "")).lower()
    if any(k in text for k in ("halloween", "할로윈", "sensory", "감각 친화")):
        return "할로윈 분위기 속에서 테마 체험과 시즌 활동을 즐길 수 있는 행사입니다."
    if any(k in text for k in ("sanrio", "캐릭터", "meet and greet")):
        return "인기 캐릭터를 가까이에서 만나고 사진을 남기기 좋은 행사입니다."
    if any(k in text for k in ("market", "마켓", "popup", "팝업")):
        return "다양한 부스와 상품을 둘러보며 주말 쇼핑과 구경을 즐길 수 있는 행사입니다."
    if any(k in text for k in ("workshop", "워크숍", "maker", "printing", "프린팅", "science", "과학")):
        return "직접 만들고 체험하며 새로운 것을 배울 수 있는 참여형 프로그램입니다."
    if any(k in text for k in ("walk", "산책", "forest", "숲")):
        return "야외에서 걷고 자연을 즐기며 여유로운 시간을 보내기 좋은 활동입니다."
    if item.get("category") == "가족·키즈":
        return "아이와 함께 참여하거나 가족 나들이 코스로 고려하기 좋은 행사입니다."
    if item.get("category") == "성인·문화":
        return "전시·공연·문화 콘텐츠를 둘러보며 주말 여가를 보내기 좋은 행사입니다."
    return "행사 세부 내용과 참여 조건은 주최 측 안내에서 확인해 주세요."

def audience_recommendation(item):
    text = (item.get("title", "") + " " + item.get("category", "")).lower()
    if any(k in text for k in ("toddler", "baby", "유아")):
        age = "영유아 동반 가족"
    elif any(k in text for k in ("kids", "kid", "children", "child", "family", "halloween", "키즈", "가족", "할로윈", "sensory", "감각 친화", "pokemon", "sanrio", "캐릭터")):
        age = "어린이·가족"
    elif any(k in text for k in ("workshop", "워크숍", "market", "마켓", "concert", "공연", "exhibition", "전시", "art", "문화")):
        age = "청소년·성인"
    else:
        age = "전 연령(세부 조건 확인)"
    return age, "남녀 모두"

def card(item, number=None, number_class=None):
    title = html.escape(korean_title(item.get("title","")) )
    link = html.escape(item.get("link","#"), quote=True)
    date = korean_date_html(clean_event_date(item.get("date","일정 원문 확인")) )
    location = html.escape(simplify_location(item.get("location","원문에서 장소 확인")))
    intro = html.escape(event_intro(item))
    age, gender = audience_recommendation(item)
    audience = html.escape(age + " · " + gender)
    price = html.escape(item.get("price","원문에서 확인"))
    source = html.escape(item.get("source",""))
    category = html.escape(item.get("category","행사"))
    number_class = number_class or ("number-family" if item.get("category") == "가족·키즈" else ("number-culture" if item.get("category") == "성인·문화" else "number-weekend"))
    number_colors = {"number-weekend": "#2563eb", "number-family": "#0891b2", "number-culture": "#d97706"}
    number_color = number_colors.get(number_class, "#2563eb")
    number_html = f'<span class="number {number_class}" style="background-color:{number_color};color:#ffffff !important">{number}</span>' if number is not None else ""
    maps_q = urllib.parse.quote(item.get("location", "Kuala Lumpur, Malaysia"))
    google_maps = "https://www.google.com/maps/search/?api=1&query=" + maps_q
    waze = "https://waze.com/ul?q=" + maps_q + "&navigate=yes"
    nav = f'<div class="nav-links"><a href="{html.escape(google_maps, quote=True)}" target="_blank" rel="noopener">📍 Google 지도 길찾기</a><a href="{html.escape(waze, quote=True)}" target="_blank" rel="noopener">🚗 Waze 길찾기</a></div>'
    return f'<article class="event">{number_html}<div class="top"><span class="pill">{category}</span><span class="source">{source}</span></div><h3><a href="{link}" target="_blank" rel="noopener">{title}</a></h3><p class="summary">{intro}</p><p class="meta">📅 {date}</p><p class="meta">📍 {location}</p><p class="meta">👥 {audience}</p><p class="meta">🎟️ {price}</p>{nav}<p><a class="detail" href="{link}" target="_blank" rel="noopener">공식/원문에서 상세 정보 확인 ↗</a></p></article>'

def holiday_card(item):
    name = html.escape(item.get("localName") or item.get("name") or "공휴일")
    date = html.escape(korean_date(item.get("date","")))
    en = html.escape(item.get("name",""))
    return f'<article class="event"><span class="pill">공휴일</span><h3>{name}</h3><p class="meta"><span class="date-holiday">{date}</span> · {en}</p></article>'

def parsed_event_dates(item):
    """Return only explicit calendar dates parsed from the source's event date string."""
    date_text = item.get("date", "")
    parsed = re.findall(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(20\d{2})", date_text, re.I)
    dates = []
    for day, month_name, year in parsed:
        try:
            dates.append(datetime.strptime(f"{day} {month_name} {year}", "%d %B %Y").date())
        except ValueError:
            continue
    return dates

def build_page(events, hols):
    # Always publish a fresh page, even when the scraper cannot verify this weekend's events.
    weekend_start = TODAY + timedelta(days=(5 - TODAY.weekday()) % 7)
    weekend_end = weekend_start + timedelta(days=1)
    this_weekend = [
        item for item in events
        if any(weekend_start <= event_day <= weekend_end for event_day in parsed_event_dates(item))
    ]
    future_events = [
        item for item in events
        if any(event_day >= TODAY for event_day in parsed_event_dates(item))
    ]
    instagram = [x for x in future_events if is_instagram_event(x) or x.get("category") == "인스타그램"]
    non_instagram = [x for x in future_events if x not in instagram]
    family = [x for x in non_instagram if x["category"] == "가족·키즈"]
    adult = [x for x in non_instagram if x["category"] != "가족·키즈"]
    if not this_weekend:
        print("NO_VERIFIED_EVENTS_FOR_UPCOMING_WEEKEND: page will be refreshed without stale event recommendations")
    stamp = NOW.strftime("%Y-%m-%d %H:%M MYT")
    def section(title, items, numbered=False, number_class="number-weekend"):
        body = "".join(card(x, i + 1 if numbered else None, number_class if numbered else None) for i, x in enumerate(items)) or '<p class="muted">현재 날짜가 확인된 행사를 찾지 못했습니다. 지난 행사 정보를 최신 행사처럼 표시하지 않습니다. 아래 공식 행사 캘린더에서 일정을 확인해 주세요.</p>'
        return f'<section><h2>{title}</h2>{body}</section>'
    content = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KL & Selangor Weekend Events</title><meta name="description" content="쿠알라룸푸르와 셀랑고르의 최신 주말 행사, 가족·키즈 활동, 성인 문화 행사와 공휴일을 확인하세요.">
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f3f6fb;color:#172033;font-family:Arial,'Noto Sans KR',sans-serif;line-height:1.6}}header{{background:linear-gradient(135deg,#172554,#334e9b);color:#fff;padding:28px 17px}}header div,main,footer{{max-width:880px;margin:auto}}h1{{margin:0;font-size:clamp(25px,6vw,36px);line-height:1.2}}header p{{color:#dbeafe;margin:9px 0 0}}main{{padding:16px 12px 38px}}.notice{{background:#fff;border:1px solid #dfe5ef;border-radius:13px;padding:14px;margin:0 0 22px}}section{{margin:0 0 26px}}h2{{font-size:21px;margin:0 0 10px}}.event{{position:relative;background:#fff;border:1px solid #dfe5ef;border-radius:13px;padding:18px 15px 15px 58px;margin:10px 0;box-shadow:0 2px 7px #1b2b4a0b}}.number{{position:absolute;left:14px;top:16px;display:flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:50%;color:#fff;font-weight:700}}.number-weekend{{background:#2563eb}}.number-family{{background:#0891b2}}.number-culture{{background:#d97706}}.nav-links{{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}}.nav-links a{{display:inline-block;background:#edf3ff;border:1px solid #d5e1fb;border-radius:8px;padding:8px 10px;text-decoration:none;font-weight:700;font-size:13px}}h3{{font-size:17px;line-height:1.4;margin:9px 0}}.summary{{font-size:14px;color:#374151;background:#f8fafc;border-left:3px solid #94a3b8;padding:8px 10px;margin:8px 0}}.meta,.muted{{color:#536078;font-size:14px;margin:5px 0;overflow-wrap:anywhere}}a{{color:#2457b5;overflow-wrap:anywhere}}.top{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}.pill{{display:inline-block;background:#e8efff;color:#253f8c;padding:3px 9px;border-radius:18px;font-size:12px;font-weight:700}}.source{{font-size:12px;color:#6b7280}}.date-sat{{color:#2563eb;font-weight:700}}.date-sun,.date-holiday{{color:#dc2626;font-weight:700}}.holiday{{border-color:#fecaca}}.detail{{display:inline-block;margin-top:5px;font-weight:700;text-decoration:none}}footer{{padding:0 14px 30px;color:#687386;font-size:12px}}
</style></head><body><header><div><h1>KL & Selangor Weekend Events</h1><p>주말에 갈 만한 행사만 모아보기 · 가족·키즈 · 성인·문화 · 공휴일</p></div></header><main>
<div class="notice"><b>마지막 업데이트:</b> {stamp}<p class="muted">날짜·장소·가격은 원문에서 추출한 정보입니다. 일정 변경 가능성이 있으니 방문 전 상세 링크에서 주최 측 공지를 확인해 주세요. 확인되지 않은 정보는 ‘원문 확인’으로 표시합니다.</p><p><a href="https://kualalumpurwithkids.com/events/month/" target="_blank" rel="noopener">가족 행사 캘린더</a> · <a href="https://discover.calendar2u.com/" target="_blank" rel="noopener">전체 행사 캘린더</a> · <a href="https://www.warisankl.my/events" target="_blank" rel="noopener">Warisan KL 문화 행사</a> · <a href="https://www.dbkl.gov.my/en" target="_blank" rel="noopener">쿠알라룸푸르 시청 행사</a></p></div>
{section("📌 다가오는 주말 추천 TOP", this_weekend[:12], numbered=True, number_class="number-weekend")}
{section("👨‍👩‍👧‍👦 가족·키즈 행사", family[:20], numbered=True, number_class="number-family")}
{section("🎭 성인·문화·공연·전시", adult[:20], numbered=True, number_class="number-culture")}
{section("📸 인스타그램 핫플·팝업·마켓·체험", instagram[:20], numbered=True, number_class="number-culture")}
<section><h2>📱 인스타그램에서 더 찾아보기</h2><article class="event"><p>인스타그램 게시물은 공개 범위와 로그인 제한 때문에 자동으로 행사 일정으로 수집되지 않을 수 있습니다. 아래에서 최신 팝업·마켓·체험 공지를 확인해 주세요.</p><div class="nav-links"><a href="https://www.instagram.com/explore/search/keyword/?q=kl%20weekend%20events" target="_blank" rel="noopener">KL 주말 행사 검색</a><a href="https://www.instagram.com/explore/search/keyword/?q=kl%20popup%20market" target="_blank" rel="noopener">팝업·마켓 검색</a><a href="https://www.instagram.com/explore/search/keyword/?q=selangor%20family%20events" target="_blank" rel="noopener">셀랑고르 가족 행사 검색</a></div></article></section>
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
    saturday = TODAY + timedelta(days=(5 - TODAY.weekday()) % 7)
    sunday = saturday + timedelta(days=1)
    weekdays_ko = ["월", "화", "수", "목", "금", "토", "일"]
    weekend_label = f"{saturday.month}월 {saturday.day}일({weekdays_ko[saturday.weekday()]}) ~ {sunday.month}월 {sunday.day}일({weekdays_ko[sunday.weekday()]})"
    if weekend:
        headline = "🎉 이번 주말 KL·셀랑고르 나들이 & 이벤트"
        teaser = f"할로윈·가족 체험·팝업 등 주말 행사 {len(weekend)}개를 모았습니다."
    else:
        headline = "🇲🇾 KL·셀랑고르 주말 행사 안내"
        teaser = "이번 주말 가볼 만한 행사와 이벤트 일정을 확인해 보세요."
    text_body = f"{headline}\n📅 {weekend_label}\n{teaser}\n\n👇 행사 일정·장소·가격·지도 보기\n{BASE}"
    message = {
        "object_type": "text",
        "text": text_body[:1900],
        "link": {"web_url": BASE, "mobile_web_url": BASE},
        "button_title": "주말 행사 보기"
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
    print(f"KAKAO_MESSAGE_SENT: short digest for {weekend_label}; {len(weekend)} dated events linked")

def main():
    events = collect_events()
    hols = holidays()
    build_page(events, hols)
    print(f"Page updated: {len(events)} dated event leads, {len(hols)} public holidays")
    kakao_send(events, hols)

if __name__ == "__main__":
    main()
