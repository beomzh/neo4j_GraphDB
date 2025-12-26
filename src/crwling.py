import os
import time
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from src.database import db
from urllib.parse import quote

class NewsToNeo4j:
    def __init__(self):
        try:
            self.driver = db.driver
        except Exception as e:
            print(f"❌ DB 연결 실패: {e}")
            self.driver = None
            
        self.log_dir = "crawl_logs"
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
            
    def save_debug_info(self, page, name):
        """에러 발생 시점의 스크린샷과 HTML 소스를 저장합니다."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.join(self.log_dir, f"{name}_{timestamp}.png")
        html_path = os.path.join(self.log_dir, f"{name}_{timestamp}.html")
        
        page.screenshot(path=screenshot_path)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page.content())
        print(f"   📸 디버그 정보 저장됨: {screenshot_path}")
        
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
                result = session.run(query, data)
                summary = result.consume()
                if summary.counters.nodes_created > 0:
                    print(f"      🏠 [DB] 새 노드 생성 완료")
                elif summary.counters.properties_set > 0:
                    print(f"      🔄 [DB] 기존 데이터 업데이트 완료")
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
            # Docker 환경 최적화 설정
            browser = p.chromium.launch(
                headless=True, 
                args=[
                    '--no-sandbox', 
                    '--disable-setuid-sandbox',
                    '--disable-blink-features=AutomationControlled'
                    ]
                )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                locale="ko-KR",
                timezone_id="Asia/Seoul"                
            )
            page = context.new_page()

            for p_num in range(pages):
                start = (p_num * 10) + 1
                # url = f"https://search.naver.com/search.naver?where=news&query={quote(keyword)}&start={start}"
                url = f"https://www.google.com/search?q={quote(keyword)}&tbm=nws&start={start}"
                print(f"\n📡 [{p_num+1}/{pages}] 페이지 요청 중: {url}")
                                
                try:
                    # 페이지 이동 및 응답 확인
                    response = page.goto(url, wait_until="domcontentloaded", timeout=10000)
                    
                    if response:
                        print(f"   📥 [상태코드] {response.status}")
                        if response.status == 429:
                            print("   🚫 구글로부터 일시적 차단(Too Many Requests)을 당했습니다. 중단합니다.")
                            break
                        if response.status != 200:
                            print(f"   ⚠️ 정상적인 응답이 아닙니다. (Status: {response.status})")
                    
                    # 뉴스 영역 확인
                    if page.query_selector("div#search"):
                        print(f"   🔎 [성공] 구글 뉴스 검색 결과 로드 완료")
                    else:
                        print(f"   ⚠️ [경고] 검색 결과 영역을 찾을 수 없습니다.")
                        self.save_debug_info(page, f"no_search_result_p{p_num+1}")
                        continue
                    
                    # 기사 리스트 추출
                    content = page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    articles = soup.find_all('div', attrs={'data-ved': True})
                    if not articles:
                        # 만약 위 방법으로도 안 잡히면 더 넓은 범위로 탐색
                        articles = soup.select('div#rso > div')
                    print(f"   📦 [추출] {len(articles)}개의 후보 기사 발견")
                    
                    for idx, art in enumerate(articles):
                        try:
                            link_tag = art.find('a', href=True)
                            if not link_tag or 'google.com' in link_tag['href']: continue 
                            
                            title_tag = link_tag.find(['div', 'h3'], attrs={'role': 'heading'})
                            if not title_tag:
                                title_tag = link_tag.find(['div', 'span']) # 더 유연하게 탐색
                                
                            if not title_tag or len(title_tag.get_text().strip()) < 5: continue

                            # 상세 페이지 본문 수집을 할 것인지 선택 (속도 vs 데이터양)
                            link = link_tag['href']
                            content = ""
                            
                            # 본문까지 긁고 싶다면 활성화
                            if True: 
                                detail_page = context.new_page()
                                content = self.get_article_content(detail_page, link)
                                detail_page.close()

                            data = {
                                'title': title_tag.get_text().strip(),
                                'link': link,
                                'publisher': art.find('span').get_text().strip() if art.find('span') else "Google News", # 변수명 통일: source -> publisher
                                'content': content
                            }
                            
                            print(f"   📝 ({idx+1}) 데이터 추출 성공: {data['title'][:20]}...")

                            if self.save_to_neo4j(data):
                                total_saved += 1
                                
                        except Exception as inner_e:
                            print(f"      ❗ [파싱 에러] {inner_e}")
                            continue
                                
                except Exception as e:
                    print(f"   ❌ [페이지 에러] {type(e).__name__}")
                    self.save_debug_info(page, f"page_error_p{p_num+1}")
                    continue
                            
                                
                            

            browser.close()
        print(f"\n✨ 최종 {total_saved}건 Neo4j 저장 완료.")
