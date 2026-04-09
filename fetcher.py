"""
Threads 최신 게시물 → oEmbed 자동 수집기 PoC

사용법:
  1. pip install playwright requests beautifulsoup4
  2. playwright install chromium
  3. python fetcher.py

매일 cron으로 실행하면 식당의 당일 메뉴를 자동 수집합니다.
"""

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from playwright.async_api import async_playwright

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
TARGET_HANDLE = "jungsuk_cafeteria1"
PROFILE_URL = f"https://www.threads.net/@{TARGET_HANDLE}"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ──────────────────────────────────────────────
# Step 1: 프로필 페이지에서 최신 게시물 URL 추출
# ──────────────────────────────────────────────
async def fetch_latest_post_url() -> dict | None:
    """
    Threads 프로필 페이지를 헤드리스 브라우저로 로드하고,
    hidden JSON 또는 DOM에서 최신 게시물 정보를 추출합니다.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="ko-KR",
        )
        page = await context.new_page()

        # ── 방법 A: 네트워크 응답에서 GraphQL 데이터 캡처 ──
        captured_posts = []

        async def on_response(response):
            url = response.url
            # Threads의 GraphQL API 응답 캡처
            if "graphql" in url or "api/v1" in url:
                try:
                    text = await response.text()
                    if TARGET_HANDLE in text and "code" in text:
                        captured_posts.append(text)
                except Exception:
                    pass

        page.on("response", on_response)

        try:
            await page.goto(PROFILE_URL, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"⚠️  페이지 로드 중 오류 (계속 진행): {e}")

        result = None

        # ── 방법 A: DOM에서 직접 추출 (가장 신뢰할 수 있음) ──
        result = await _extract_from_dom(page)
        if result:
            print("✅ DOM에서 추출 성공")

        # ── 방법 B: GraphQL 응답 파싱 (fallback) ──
        if not result:
            for raw in captured_posts:
                try:
                    data = json.loads(raw)
                    result = _extract_from_graphql(data)
                    if result:
                        print("✅ GraphQL 응답에서 추출 성공")
                        break
                except json.JSONDecodeError:
                    continue

        # ── 방법 C: hidden <script> JSON 파싱 (fallback) ──
        if not result:
            result = await _extract_from_hidden_json(page)
            if result:
                print("✅ Hidden JSON에서 추출 성공")

        await browser.close()
        return result


def _extract_from_graphql(data: dict) -> dict | None:
    """GraphQL 응답 JSON에서 최신 게시물 정보 추출"""
    try:
        # Threads GraphQL 응답 구조 탐색
        # 구조는 변경될 수 있으므로 여러 경로 시도
        threads = _deep_find(data, "threads") or _deep_find(data, "edges")
        if not threads:
            return None

        if isinstance(threads, list) and len(threads) > 0:
            first = threads[0]
            node = first.get("node", first)
            code = (
                node.get("code")
                or _deep_find(node, "code")
            )
            text = (
                node.get("text")
                or _deep_find(node, "caption", {}).get("text", "")
                or _deep_find(node, "text")
            )
            taken_at = node.get("taken_at") or _deep_find(node, "taken_at")

            if code:
                return {
                    "shortcode": code,
                    "url": f"https://www.threads.net/@{TARGET_HANDLE}/post/{code}",
                    "text": text or "",
                    "timestamp": taken_at,
                    "method": "graphql",
                }
    except Exception:
        pass
    return None


async def _extract_from_dom(page) -> dict | None:
    """렌더링된 DOM에서 게시물 링크 및 본문 추출"""
    try:
        links = await page.evaluate(
            """() => {
                const anchors = document.querySelectorAll('a[href*="/post/"]');
                return Array.from(anchors).map(a => {
                    const container = a.closest('[data-pressable-container]');
                    let text = '';
                    let images = [];
                    if (container) {
                        // [dir="auto"] span 중 유저네임이 아닌 본문 텍스트를 수집
                        const spans = container.querySelectorAll('span[dir="auto"]');
                        const parts = [];
                        spans.forEach(s => {
                            const t = s.textContent.trim();
                            // 유저네임, 짧은 UI 텍스트 제외
                            if (t.length > 10 && !s.querySelector('a')
                                && !t.match(/^[a-zA-Z0-9_.]+$/)) {
                                parts.push(t);
                            }
                        });
                        text = parts.join('\\n');

                        // 게시물 이미지 추출 (프로필 사진 등 작은 이미지 제외)
                        const imgs = container.querySelectorAll('img');
                        imgs.forEach(img => {
                            if (img.width > 100 && img.src) {
                                images.push(img.src);
                            }
                        });
                    }
                    return {
                        href: a.href,
                        time: a.querySelector('time')?.getAttribute('datetime') || null,
                        text: text,
                        images: images,
                    };
                });
            }"""
        )
        if links:
            first = links[0]
            match = re.search(r"/post/([A-Za-z0-9_-]+)", first["href"])
            if match:
                shortcode = match.group(1)
                return {
                    "shortcode": shortcode,
                    "url": f"https://www.threads.net/@{TARGET_HANDLE}/post/{shortcode}",
                    "text": first.get("text", ""),
                    "timestamp": first.get("time"),
                    "images": first.get("images", []),
                    "method": "dom",
                }
    except Exception:
        pass
    return None


async def _extract_from_hidden_json(page) -> dict | None:
    """<script> 태그 안의 hidden JSON 데이터 파싱"""
    try:
        scripts = await page.evaluate(
            """() => {
                return Array.from(document.querySelectorAll('script'))
                    .map(s => s.textContent)
                    .filter(t => t && t.length > 1000);
            }"""
        )
        for script_text in scripts:
            # JSON 블록 찾기
            for match in re.finditer(r'\{".+?\}', script_text):
                try:
                    chunk = json.loads(match.group())
                    code = _deep_find(chunk, "code")
                    if code and len(code) > 5:
                        text_content = _deep_find(chunk, "text") or ""
                        return {
                            "shortcode": code,
                            "url": f"https://www.threads.net/@{TARGET_HANDLE}/post/{code}",
                            "text": text_content,
                            "timestamp": _deep_find(chunk, "taken_at"),
                            "method": "hidden_json",
                        }
                except (json.JSONDecodeError, RecursionError):
                    continue
    except Exception:
        pass
    return None


def _deep_find(obj, key, default=None):
    """중첩 딕셔너리에서 key를 재귀적으로 탐색"""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            result = _deep_find(v, key, default)
            if result is not default:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _deep_find(item, key, default)
            if result is not default:
                return result
    return default


# ──────────────────────────────────────────────
# Step 2: oEmbed API 호출
# ──────────────────────────────────────────────
def fetch_oembed(post_url: str) -> dict | None:
    """
    Threads embed 데이터를 가져옵니다.
    graph.threads.net oEmbed API가 토큰을 요구하므로,
    /embed 페이지를 iframe src로 사용하는 방식으로 대체합니다.
    """
    # post_url 도메인을 threads.com으로 통일
    embed_url = post_url.replace("threads.net", "threads.com")
    if not embed_url.endswith("/"):
        embed_url += "/embed"
    else:
        embed_url += "embed"

    try:
        resp = requests.get(
            embed_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        if resp.status_code == 200:
            embed_html = (
                f'<iframe src="{embed_url}" '
                f'width="550" height="700" '
                f'frameborder="0" scrolling="no" '
                f'allowtransparency="true"></iframe>'
            )
            return {
                "html": embed_html,
                "width": 550,
                "embed_url": embed_url,
                "author_name": TARGET_HANDLE,
            }
        else:
            print(f"⚠️  embed 페이지 응답 {resp.status_code}")
            return None
    except Exception as e:
        print(f"❌ embed 호출 실패: {e}")
        return None


# ──────────────────────────────────────────────
# Step 3: 결과 저장
# ──────────────────────────────────────────────
def save_result(post_info: dict, oembed_data: dict | None):
    """당일 메뉴 데이터를 JSON 파일로 저장"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = {
        "date": today,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "post": post_info,
        "oembed": oembed_data,
    }

    output_file = OUTPUT_DIR / f"menu_{today}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"💾 저장 완료: {output_file}")
    return result


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
async def main():
    print(f"🔍 [{TARGET_HANDLE}] 최신 게시물 조회 중...\n")

    # Step 1: 최신 게시물 URL 추출
    post_info = await fetch_latest_post_url()

    if not post_info:
        print("❌ 최신 게시물을 찾을 수 없습니다.")
        print("   → 프로필이 비공개이거나, Threads 페이지 구조가 변경되었을 수 있습니다.")
        sys.exit(1)

    print(f"\n📌 최신 게시물:")
    print(f"   URL:  {post_info['url']}")
    print(f"   Text: {post_info['text'][:80]}...")
    print(f"   Time: {post_info.get('timestamp', 'N/A')}")
    print(f"   추출: {post_info['method']}")

    # Step 2: oEmbed 호출
    print(f"\n🔗 oEmbed API 호출 중...")
    oembed_data = fetch_oembed(post_info["url"])

    if oembed_data:
        print(f"   ✅ embed HTML 수신 ({len(oembed_data.get('html', ''))} chars)")
    else:
        print(f"   ⚠️  oEmbed 실패 (게시물 URL은 확보됨, embed 없이 저장)")

    # Step 3: 저장
    result = save_result(post_info, oembed_data)

    # 요약
    print(f"\n{'='*50}")
    print(f"✅ 완료! 결과: output/menu_{result['date']}.json")
    print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(main())
