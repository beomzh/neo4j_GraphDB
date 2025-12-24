import os
import time
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

uri = os.getenv("NEO4J_URI", "bolt://10.20.1.91:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "openmaru")

def test_connection():
    retry_count = 5
    while retry_count > 0:
        try:
            print(f"🔄 Neo4j 연결 시도 중... (남은 횟수: {retry_count})")
            driver = GraphDatabase.driver(uri, auth=(user, password))
            with driver.session() as session:
                result = session.run("RETURN 'Hello Neo4j from Docker!' AS message")
                record = result.single()
                print(f"\n✅ 결과: {record['message']}\n")
                return # 성공 시 함수 종료
        except ServiceUnavailable as e:
            print(f"⚠️ 연결 실패 (서버가 아직 준비 안 됨): {e}")
            retry_count -= 1
            time.sleep(5) # 5초 후 재시도
        finally:
            if 'driver' in locals():
                driver.close()
    
    print("❌ 최종 연결 실패")

if __name__ == "__main__":
    test_connection()
