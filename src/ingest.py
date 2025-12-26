from src.database import db

def insert_user(name, tech):
    query = """
    MERGE (u:User {name: $name})
    MERGE (t:Tech {name: $tech})
    MERGE (u)-[:INTERESTED_IN]->(t)
    """
    with db.driver.session() as session:
        session.run(query, name=name, tech=tech)
        print(f"✅ {name} 데이터 삽입 완료")
