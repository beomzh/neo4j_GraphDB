# from src.ingest import insert_user
from src.crwling import NewsToNeo4j
from src.database import db

def main():
    print("실행합니다.")
    # test 데이터 삽입
    # try:
    #     insert_user("Beomzh", "GraphRAG")
    # finally:
    #     db.close() # 프로그램 종료 시 공통 드라이버 닫기
    app_crawler = NewsToNeo4j()
    try:
        search_keyword = "연예"
        app_crawler.crawl(search_keyword, pages=3) # 2페이지 크롤링
        with db.driver.session() as session:
            result = session.run("MATCH (a:Article) RETURN a.title AS title LIMIT 5")
            records = list(result)
            if not records:
                print("데이터가 아직 DB에 없습니다. 쿼리를 확인하세요.")
            for record in records:
                print(f"저장된 기사: {record['title']}")
        print("\n모든 데이터가 Neo4j에 성공적으로 저장되었습니다.")
    finally:
        app_crawler.close()
    
            
if __name__ == "__main__":
    main()
    
    
