"""
menu JSON → HTML 메뉴판 생성기
fetcher.py 실행 후 이 스크립트를 실행하면
docs/index.html 을 생성합니다. (GitHub Pages 용)
"""

import json
import sys
from datetime import datetime
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
        images_html += f'    <img src="{img_url}" alt="메뉴 사진" loading="lazy">\n'

    thread_url = post["url"]

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{display_date} 메뉴</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #fafafa;
    color: #333;
    padding: 20px;
    max-width: 680px;
    margin: 0 auto;
  }}
  .header {{
    text-align: center;
    padding: 24px 0 16px;
    border-bottom: 2px solid #eee;
    margin-bottom: 20px;
  }}
  .header h1 {{
    font-size: 1.5rem;
    font-weight: 700;
    color: #111;
  }}
  .header .date {{
    font-size: 1.1rem;
    color: #666;
    margin-top: 4px;
  }}
  .header .updated {{
    font-size: 0.8rem;
    color: #999;
    margin-top: 8px;
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
  .photos {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    margin-bottom: 20px;
  }}
  .photos img {{
    width: 100%;
    border-radius: 8px;
    aspect-ratio: 1;
    object-fit: cover;
  }}
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
  <h1>정석 구내식당</h1>
  <div class="date">{display_date}</div>
  <div class="updated">업데이트: {data["fetched_at"][:16].replace("T", " ")} UTC</div>
</div>

<div class="menu-text">
  {text_html}
</div>

<div class="photos">
{images_html}</div>

<div class="source">
  <a href="{thread_url}" target="_blank">Threads 원본 보기 &rarr;</a>
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
