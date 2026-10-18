import os, html, json, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

BASE = "https://chronixgames.github.io/kl-weekend-events/"
MYT = timezone(timedelta(hours=8))
NOW = datetime.now(MYT)
START = NOW.date()
END = START + timedelta(days=21)

def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "KLWeekendEventsBot/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()

def rss_items(query, limit=8):
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(query) + "&hl=en-MY&gl=MY&ceid=MY:en"
    try:
        root = ET.fromstring(get(url))
        out = []
        for item in root.findall(".//item")[:limit]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            source = item.findtext("source") or "Google News"
            if title and link:
                out.append({"title": title, "link": link, "date": pub, "source": source})
        return out
    except Exception:
        return []

def holidays():
    url = f"https://date.nager.at/api/v3/PublicHolidays/{START.year}/MY"
    try:
        data = json.loads(get(url))
        return [x for x in data if START.isoformat() <= x.get("date","") <= END.isoformat()]
    except Exception:
        return []

def card(item, kind="event"):
    title = html.escape(item.get("title",""))
    link = html.escape(item.get("link","#"), quote=True)
    date = html.escape(item.get("date",""))
    source = html.escape(item.get("source",""))
    return f'<article class="event"><span class="pill">{html.escape(kind)}</span><h3><a href="{link}" target="_blank" rel="noopener">{title}</a></h3><p class="meta">{date} · {source}</p><p>세부 일정과 장소는 원문 링크에서 확인해 주세요. 방문 전 주최 측 공식 안내를 확인해 주세요.</p><p><a href="{link}" target="_blank" rel="noopener">출처 및 상세 정보 →</a></p></article>'

def holiday_card(item):
    name = html.escape(item.get("localName") or item.get("name") or "공휴일")
    date = html.escape(item.get("date",""))
    name_en = html.escape(item.get("name",""))
    return f'<article class="event"><span class="pill">말레이시아 공휴일</span><h3>{name}</h3><p class="meta">{date} · {name_en}</p></article>'

def build_page(events, insta, hols):
    def section(title, items, render):
        body = "".join(render(x) for x in items) or '<p class="muted">현재 확인된 항목이 없습니다. 다음 자동 업데이트 때 다시 확인합니다.</p>'
        return f'<section><h2>{title}</h2>{body}</section>'
    stamp = NOW.strftime("%Y-%m-%d %H:%M MYT")
    content = f"""
<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KL & Selangor Weekend Events</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f4f6fb;color:#202938;font-family:Arial,'Noto Sans KR',sans-serif;line-height:1.65}}
header{{background:#172554;color:white;padding:30px 18px}}header div,main,footer{{max-width:900px;margin:auto}}h1{{margin:0;font-size:clamp(26px,5vw,38px)}}header p{{color:#dbeafe;margin:5px 0 0}}
main{{padding:20px 14px 45px}}section,.notice{{margin:0 0 24px}}h2{{font-size:23px;margin:0 0 12px}}.event,.notice{{background:white;border:1px solid #e1e6ef;border-radius:14px;padding:17px;margin:12px 0}}
.event h3{{font-size:18px;margin:6px 0}}.meta,.muted{{color:#667085;font-size:14px}}a{{color:#3157a4;overflow-wrap:anywhere}}.pill{{display:inline-block;background:#eef2ff;color:#3730a3;padding:2px 10px;border-radius:18px;font-size:12px}}footer{{padding:20px 14px 35px;color:#667085;font-size:13px}}
</style></head><body><header><div><h1>KL & Selangor Weekend Events</h1><p>쿠알라룸푸르 · 셀랑고르 주말 행사 / 가족·키즈·성인 행사·인스타그램 소식·공휴일</p></div></header>
<main><div class="notice"><strong>마지막 업데이트:</strong> {stamp}<p class="muted">검색 결과는 행사 정보의 발견을 위한 참고 자료입니다. 행사 날짜·시간·장소 및 예약 가능 여부는 원문 또는 주최 측 공식 채널에서 꼭 확인해 주세요.</p></div>
{section("🎪 KL·셀랑고르 행사 소식", events, lambda x: card(x,"행사 소식"))}
{section("📸 Instagram 관련 행사 소식", insta, lambda x: card(x,"Instagram 관련 검색"))}
{section("🇲🇾 다가오는 말레이시아 공휴일", hols, holiday_card)}
</main><footer>KL & Selangor Weekend Events · 자동 검색 결과이며 모든 항목이 확정·검증된 행사는 아닙니다.</footer></body></html>"""
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html","w",encoding="utf-8") as f: f.write(content)

def kakao_send():
    rest = os.environ["KAKAO_REST_API_KEY"]
    access = os.environ.get("KAKAO_ACCESS_TOKEN","")
    refresh = os.environ.get("KAKAO_REFRESH_TOKEN","")
    secret = os.environ.get("KAKAO_CLIENT_SECRET","")
    message = {"object_type":"text","text":"이번 주말 KL·셀랑고르 행사 안내가 업데이트되었습니다. 행사 상세 정보와 출처 링크를 아래 페이지에서 확인해 주세요.","link":{"web_url":BASE,"mobile_web_url":BASE},"button_title":"행사 상세 보기"}
    def send(token):
        payload = urllib.parse.urlencode({"template_object":json.dumps(message,ensure_ascii=False)}).encode()
        req = urllib.request.Request("https://kapi.kakao.com/v2/api/talk/memo/send",data=payload,headers={"Authorization":"Bearer "+token,"Content-Type":"application/x-www-form-urlencoded;charset=utf-8"})
        try:
            with urllib.request.urlopen(req,timeout=25) as r: return r.read().decode()
        except urllib.error.HTTPError as e:
            return "HTTP_ERROR:"+str(e.code)+":"+e.read().decode()
    result = send(access) if access else "NO_ACCESS_TOKEN"
    if result.startswith("HTTP_ERROR:401") and refresh:
        form = {"grant_type":"refresh_token","client_id":rest,"refresh_token":refresh}
        if secret: form["client_secret"] = secret
        req = urllib.request.Request("https://kauth.kakao.com/oauth/token",data=urllib.parse.urlencode(form).encode(),headers={"Content-Type":"application/x-www-form-urlencoded;charset=utf-8"})
        with urllib.request.urlopen(req,timeout=25) as r: token_data=json.loads(r.read().decode())
        access = token_data["access_token"]
        result = send(access)
        print("KAKAO_ACCESS_TOKEN_REFRESHED")
        if token_data.get("refresh_token"):
            print("A_REFRESH_TOKEN_WAS_ROTATED")
    if not result.startswith("{") or '"result_code":0' not in result:
        raise RuntimeError("Kakao message send failed. Check token/secrets. Response: "+result[:400])
    print("KAKAO_MESSAGE_SENT")

def main():
    events = rss_items('(family OR kids OR children OR festival OR market OR exhibition) (Kuala Lumpur OR Selangor) event', 10)
    insta = rss_items('site:instagram.com (Kuala Lumpur OR Selangor) event weekend', 8)
    hols = holidays()
    build_page(events, insta, hols)
    print(f"Page updated: {len(events)} event leads, {len(insta)} Instagram search leads, {len(hols)} holidays")
    kakao_send()

if __name__ == "__main__":
    main()
