"""Neo4j database connection manager with connection pooling and retry logic."""

from neo4j import GraphDatabase, AsyncGraphDatabase
from contextlib import contextmanager, asynccontextmanager
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger
from app.config import settings


class Neo4jConnection:
    """Manages Neo4j driver lifecycle and provides session factories."""

    _driver = None
    _async_driver = None

    @classmethod
    def get_driver(cls):
        if cls._driver is None:
            cls._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                max_connection_pool_size=50,
                connection_acquisition_timeout=30,
            )
            logger.info(f"Neo4j sync driver created for {settings.NEO4J_URI}")
        return cls._driver

    @classmethod
    def get_async_driver(cls):
        if cls._async_driver is None:
            cls._async_driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                max_connection_pool_size=50,
            )
            logger.info(f"Neo4j async driver created for {settings.NEO4J_URI}")
        return cls._async_driver

    @classmethod
    def close(cls):
        if cls._driver:
            cls._driver.close()
            cls._driver = None
        if cls._async_driver:
            cls._async_driver.close()
            cls._async_driver = None
        logger.info("Neo4j drivers closed")

    @classmethod
    @contextmanager
    def get_session(cls):
        driver = cls.get_driver()
        session = driver.session(database=settings.NEO4J_DATABASE)
        try:
            yield session
        finally:
            session.close()

    @classmethod
    @asynccontextmanager
    async def get_async_session(cls):
        driver = cls.get_async_driver()
        session = driver.session(database=settings.NEO4J_DATABASE)
        try:
            yield session
        finally:
            await session.close()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def execute_query(cypher: str, parameters: dict = None):
    """Execute a Cypher query with retry logic. Returns list of record dicts."""
    with Neo4jConnection.get_session() as session:
        result = session.run(cypher, parameters or {})
        records = [record.data() for record in result]
        logger.debug(f"Query returned {len(records)} records")
        return records


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def execute_write(cypher: str, parameters: dict = None):
    """Execute a write Cypher query with retry logic."""
    with Neo4jConnection.get_session() as session:
        result = session.run(cypher, parameters or {})
        summary = result.consume()
        logger.debug(
            f"Write query: {summary.counters.nodes_created} nodes, "
            f"{summary.counters.relationships_created} rels created"
        )
        return summary


async def async_execute_query(cypher: str, parameters: dict = None):
    """Async version of execute_query."""
    async with Neo4jConnection.get_async_session() as session:
        result = await session.run(cypher, parameters or {})
        records = [record.data() async for record in result]
        return records


async def async_execute_write(cypher: str, parameters: dict = None):
    """Async version of execute_write."""
    async with Neo4jConnection.get_async_session() as session:
        result = await session.run(cypher, parameters or {})
        summary = await result.consume()
        return summary


def verify_connectivity():
    """Verify Neo4j is reachable."""
    try:
        driver = Neo4jConnection.get_driver()
        driver.verify_connectivity()
        logger.info("Neo4j connectivity verified")
        return True
    except Exception as e:
        logger.error(f"Neo4j connectivity check failed: {e}")
        return False
