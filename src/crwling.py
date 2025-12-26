import time
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from src.database import db
from urllib.parse import quote

class NaverNewsToNeo4j:
    def __init__(self):
        self.driver = db.driver

    def close(self):
        self.driver.close()

    def clean_text(self, text):
        """본문 텍스트 정제 (특수문자 및 불필요한 공백 제거)"""
        if not text: return ""
        text = re.sub(r'<[^>]*>', '', text) # HTML 태그 제거
        text = text.replace('\n', ' ').replace('\t', ' ').replace('\r', ' ')
        text = text.replace('\u200b', '').strip()
        return text

    def save_to_neo4j(self, data):
        """기사, 언론사, 그리고 본문(content)을 포함하여 저장"""
        query = """
        MERGE (a:Article {link: $link})
        SET a.title = $title, 
            a.content = $content, 
            a.published_at = datetime()
        WITH a
        MERGE (p:Publisher {name: $publisher})
        MERGE (a)-[:WRITTEN_BY]->(p)
        RETURN a
        """
        try:
            with self.driver.session() as session:
                session.run(query, data)
                return True
        except Exception as e:
            print(f"   ❌ DB 저장 에러: {e}")
            return False

    def get_article_content(self, page, url):
        """기사 상세 페이지에 접속하여 본문을 추출 (참고 코드의 iframe 로직 반영)"""
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=10000)
            # 네이버 뉴스나 블로그는 특정 컨테이너 안에 본문이 있음
            # 여러 선택자를 시도하여 본문을 찾음
            content_selectors = [
                "#dic_area", "#articleBodyContents", ".se-main-container", "#articleBody"
            ]
            
            for selector in content_selectors:
                element = page.query_selector(selector)
                if element:
                    return self.clean_text(element.inner_text())
            return ""
        except:
            return ""

    def crawl(self, keyword, pages=1):
        total_saved = 0
        
        with sync_playwright() as p:
            # Docker 환경에서는 반드시 no-sandbox 옵션이 필요할 수 있음
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            for p_num in range(pages):
                start = (p_num * 10) + 1
                url = f"https://search.naver.com/search.naver?where=news&query={quote(keyword)}&start={start}"
                
                print(f"🔎 페이지 {p_num + 1} 접속 중...")
                page.goto(url, wait_until="domcontentloaded")
                
                try:
                    page.wait_for_selector(".news_tit", timeout=10000)
                except:
                    print(f"⚠️ {p_num + 1}페이지 로딩 실패 (캡차 가능성)")
                    continue

                # 기사 리스트 추출
                content = page.content()
                soup = BeautifulSoup(content, 'html.parser')
                articles = soup.select('div.news_area')

                for art in articles:
                    title_tag = art.select_one('a.news_tit')
                    press_tag = art.select_one('a.info.press')
                    
                    if not title_tag: continue
                    
                    link = title_tag['href']
                    title = title_tag.get_text(strip=True)
                    publisher = press_tag.get_text(strip=True) if press_tag else "알수없음"

                    # [핵심 보완] 상세 페이지 들어가서 본문 가져오기
                    detail_page = context.new_page()
                    article_content = self.get_article_content(detail_page, link)
                    detail_page.close()

                    data = {
                        'title': title,
                        'link': link,
                        'publisher': publisher,
                        'content': article_content
                    }
                    
                    if self.save_to_neo4j(data):
                        print(f"   ✅ [저장] {title[:20]}...")
                        total_saved += 1
                    
                    time.sleep(1) # 차단 방지를 위한 짧은 휴식

            browser.close()
        print(f"\n✨ 최종 {total_saved}건 Neo4j 저장 완료.")
