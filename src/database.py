from neo4j import GraphDatabase
from src import config

class Neo4jManager:
    def __init__(self):
        # config 모듈에서 설정값 가져오기
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI, 
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )

    def close(self):
        self.driver.close()

# 다른 파일에서 이 변수를 import해서 공통으로 사용함
db = Neo4jManager()
