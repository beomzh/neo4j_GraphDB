docker rm -f neo4j || true
docker rmi -f neo4j-test || true
docker build -t neo4j-test .
docker run -d --name neo4j \
 -p 7687:7687 \
 -p 7474:7474 \
 neo4j-test

docker logs -f neo4j
