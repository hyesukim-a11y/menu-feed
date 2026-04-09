"""
menu JSON → HTML 메뉴판 생성기
fetcher.py 실행 후 이 스크립트를 실행하면
docs/index.html 을 생성합니다. (GitHub Pages 용)
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"
DOCS_DIR = Path(__file__).parent / "docs"
DOCS_DIR.mkdir(exist_ok=True)


def find_latest_json() -> Path | None:
    files = sorted(OUTPUT_DIR.glob("menu_*.json"), reverse=True)
    return files[0] if files else None


def build_html(data: dict) -> str:
    post = data["post"]
    date_str = data["date"]
    dt = datetime.fromisoformat(date_str)
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    day_name = weekdays[dt.weekday()]
    display_date = f"{dt.month}월 {dt.day}일 ({day_name})"

    # 메뉴 텍스트를 줄바꿈 처리
    text_html = post["text"].replace("\n", "<br>")

    # 이미지 태그 생성 (최대 6장)
    images = post.get("images", [])[:6]
    images_html = ""
    for img_url in images:
        images_html += f'      <img src="{img_url}" alt="메뉴 사진" loading="lazy">\n'
    dots_html = ""
    for i in range(len(images)):
        active = ' class="active"' if i == 0 else ""
        dots_html += f'    <span{active}></span>\n'

    thread_url = post["url"]

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>{display_date} 메뉴</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #fff;
    color: #333;
    padding: 20px;
    max-width: 680px;
    margin: 0 auto;
  }}
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 8px 0 12px;
    margin-bottom: 8px;
  }}
  .header .date {{
    font-size: 0.9rem;
    font-weight: 700;
    color: #999;
  }}
  .header .updated {{
    font-size: 0.8rem;
    color: #999;
  }}
  .menu-text {{
    background: #fff;
    border: 1px solid #eee;
    border-radius: 12px;
    padding: 20px;
    font-size: 1rem;
    line-height: 1.8;
    margin-bottom: 20px;
  }}
  .carousel {{
    position: relative;
    overflow: hidden;
    border-radius: 12px;
    margin-bottom: 20px;
  }}
  .carousel-track {{
    display: flex;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }}
  .carousel-track::-webkit-scrollbar {{ display: none; }}
  .carousel-track img {{
    flex: 0 0 100%;
    width: 100%;
    aspect-ratio: 1;
    object-fit: cover;
    scroll-snap-align: start;
  }}
  .carousel-btn {{
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    background: rgba(0,0,0,0.4);
    color: #fff;
    border: none;
    font-size: 1.5rem;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.2s;
    z-index: 1;
  }}
  .carousel:hover .carousel-btn {{ opacity: 1; }}
  .carousel-btn.prev {{ left: 8px; }}
  .carousel-btn.next {{ right: 8px; }}
  .carousel-dots {{
    text-align: center;
    padding: 8px 0;
  }}
  .carousel-dots span {{
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ccc;
    margin: 0 4px;
    transition: background 0.2s;
  }}
  .carousel-dots span.active {{ background: #666; }}
  .source {{
    text-align: center;
    padding: 16px 0;
  }}
  .source a {{
    color: #666;
    font-size: 0.85rem;
    text-decoration: none;
  }}
  .source a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<div class="header">
  <div class="date">{display_date}</div>
  <div class="updated">업데이트: {(datetime.fromisoformat(data["fetched_at"]) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")}</div>
</div>

<div class="carousel">
  <button class="carousel-btn prev" onclick="slide(-1)">&lsaquo;</button>
  <div class="carousel-track">
{images_html}  </div>
  <button class="carousel-btn next" onclick="slide(1)">&rsaquo;</button>
</div>
<div class="carousel-dots">
{dots_html}</div>

<script>
(function() {{
  const track = document.querySelector('.carousel-track');
  const dots = document.querySelectorAll('.carousel-dots span');
  let idx = 0;
  const total = dots.length;

  function update() {{
    track.scrollTo({{ left: track.clientWidth * idx, behavior: 'smooth' }});
    dots.forEach((d, i) => d.classList.toggle('active', i === idx));
  }}

  window.slide = function(dir) {{
    idx = (idx + dir + total) % total;
    update();
  }};

  track.addEventListener('scrollend', () => {{
    idx = Math.round(track.scrollLeft / track.clientWidth);
    dots.forEach((d, i) => d.classList.toggle('active', i === idx));
  }});
}})();
</script>

<div class="source">
</div>
</body>
</html>"""


def main():
    json_path = find_latest_json()
    if not json_path:
        print("JSON 파일이 없습니다. fetcher.py를 먼저 실행하세요.")
        sys.exit(1)

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    html = build_html(data)
    out = DOCS_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"HTML 생성 완료: {out}")


if __name__ == "__main__":
    main()
