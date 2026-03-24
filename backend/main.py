import logging
import concurrent.futures
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

from langchain_community.graphs import Neo4jGraph
from langchain_groq import ChatGroq
from langchain.chains import GraphCypherQAChain
from langchain.prompts import PromptTemplate
from neo4j import GraphDatabase, exceptions as neo4j_exceptions

# ---------------------------------------------------------------------------
# Configuration & Logging setup
# ---------------------------------------------------------------------------
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    neo4j_uri: str = Field(default="bolt://localhost:7687", env="NEO4J_URI")
    neo4j_username: str = Field(default="neo4j", env="NEO4J_USERNAME")
    neo4j_password: str = Field(default="password", env="NEO4J_PASSWORD")
    neo4j_database: Optional[str] = Field(default=None, env="NEO4J_DATABASE")
    groq_api_key: str = Field(..., env="GROQ_API_KEY")
    timeout_seconds: int = 45

settings = Settings()

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
CYPHER_GENERATION_TEMPLATE = """Task: Generate a Cypher statement to query a graph database.

CRITICAL INSTRUCTIONS (FAILURE TO FOLLOW WILL BREAK THE SYSTEM):
1. Schema Compliance: Use ONLY the exact relationship types and properties in the schema.
2. Undirected Paths: Omit arrows. Use `()-[]-()` instead of `()->()`.
3. UNION Syntax: If you use UNION, every subquery MUST return the exact same column aliases.
4. Broken Flows: To find "delivered not billed" OR "billed without delivery", USE THIS EXACT QUERY STRUCTURE:
   `MATCH (so:SalesOrder)-[]-(od:OutboundDelivery) WHERE NOT EXISTS {{ (od)-[]-(:BillingDocument) }} RETURN so.order_id AS order_id, 'Delivered not billed' AS status LIMIT 5
   UNION
   MATCH (so:SalesOrder)-[]-(bd:BillingDocument) WHERE NOT EXISTS {{ (so)-[]-(:OutboundDelivery) }} RETURN so.order_id AS order_id, 'Billed without delivery' AS status LIMIT 5`
5. Trace Flow (Sample): If no ID is provided, find ONE successful path. 
   Example: `MATCH path=(:SalesOrder)-[*1..4]-(:JournalEntry) RETURN [n IN nodes(path) | coalesce(n.order_id, n.document_id, n.delivery_id, n.entry_id)] AS flow LIMIT 1`
6. Max/Highest & Ties: ALWAYS use `LIMIT 5` instead of `LIMIT 1` when ordering by count to catch ties.
7. Return Limits: NEVER return entire nodes (`RETURN n`). Return properties.

Schema:
{schema}

Return ONLY the valid Cypher statement. Do not include explanations.

Question:
{question}
"""

QA_PROMPT = """You are a helpful data analyst assisting with an Order-to-Cash graph database.

Context from database:
{context}

Question: {question}

Instructions:
1. Translate the raw database context into a clear, natural language response.
2. If the user asks for a general example without specifying an ID, the context will provide a sample flow array. Format that array into a readable sequence (e.g., "Here is a sample flow: Order X -> Delivery Y -> Billing Z").
3. If the context is empty ([]), respond EXACTLY with: "Based on the available data, there are no records matching that criteria."
4. Do not say "Based on the context". Just present the information naturally.

Answer:"""

# ---------------------------------------------------------------------------
# Models & Globals
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    query: str
    history: List[Dict[str, str]] = []

class QueryResponse(BaseModel):
    response: str

class RouterOutput(BaseModel):
    allowed: bool
    standalone_query: str

# Global state
app_state: Dict[str, Any] = {}

# ---------------------------------------------------------------------------
# Core Services & Lifecycle
# ---------------------------------------------------------------------------
def resolve_neo4j_database() -> str:
    """Attempts to resolve the default database name if none is provided."""
    if settings.neo4j_database:
        return settings.neo4j_database
    
    try:
        driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password))
        with driver.session() as session:
            res = session.run("CALL db.info() YIELD name RETURN name")
            for r in res:
                return r["name"]
    except neo4j_exceptions.Neo4jError as e:
        logger.warning(f"Could not resolve default database automatically: {e}")
    return "neo4j"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for establishing and tearing down database/LLM connections."""
    logger.info("Initializing Graph Connection and LLM Chains...")
    try:
        db_name = resolve_neo4j_database()
        graph = Neo4jGraph(
            url=settings.neo4j_uri, 
            username=settings.neo4j_username, 
            password=settings.neo4j_password, 
            database=db_name
        )
        
        llm = ChatGroq(
            groq_api_key=settings.groq_api_key,
            model_name="llama-3.3-70b-versatile",
            temperature=0
        )
        
        cypher_prompt = PromptTemplate(input_variables=["schema", "question"], template=CYPHER_GENERATION_TEMPLATE)
        qa_prompt = PromptTemplate(input_variables=["context", "question"], template=QA_PROMPT)
        
        chain = GraphCypherQAChain.from_llm(
            cypher_llm=llm,
            qa_llm=llm,
            graph=graph,
            verbose=True,
            cypher_prompt=cypher_prompt,
            qa_prompt=qa_prompt,
            allow_dangerous_requests=True,
            validate_cypher=True,
            return_intermediate_steps=False,
            top_k=10
        )
        
        app_state["graph"] = graph
        app_state["chain"] = chain
        app_state["llm"] = llm
        logger.info("Initialization complete.")
        yield
    except Exception as e:
        logger.error(f"Failed to initialize application state: {e}")
        raise
    finally:
        logger.info("Shutting down services...")
        app_state.clear()

app = FastAPI(title="Nexus O2C Graph Engine", lifespan=lifespan)

# ---------------------------------------------------------------------------
# API Endpoints & Logic
# ---------------------------------------------------------------------------
def rephrase_and_route(query: str, history: List[Dict[str, str]], llm: ChatGroq) -> RouterOutput:
    """Evaluates query intent and resolves context based on chat history."""
    formatted_history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-4:]]) if history else ""
    prompt = f"""You are an intelligent router for a Supply Chain Order-to-Cash Graph database AI.
Given the conversation history and the latest user query:
1. Determine if the query is allowed (related to supply chain, billing, orders, customers, deliveries, products).
2. If allowed, rewrite the query to be a fully standalone question resolving pronouns. If no history, leave query as is.

Respond ONLY with a valid JSON object matching this schema:
{{ "allowed": true or false, "standalone_query": "string" }}

History:
{formatted_history}

Latest Query: {query}
JSON Output:"""
    
    import json
    try:
        response = llm.invoke(prompt)
        content = response.content.replace('```json', '').replace('```', '').strip()
        data = json.loads(content)
        return RouterOutput(allowed=data.get("allowed", True), standalone_query=data.get("standalone_query", query))
    except Exception as e:
        logger.warning(f"Routing logic failed, defaulting to passthrough. Error: {e}")
        return RouterOutput(allowed=True, standalone_query=query)

@app.post("/chat", response_model=QueryResponse)
def chat_endpoint(request: QueryRequest):
    """Main endpoint for processing natural language to graph queries."""
    chain = app_state.get("chain")
    llm = app_state.get("llm")
    graph = app_state.get("graph")
    
    if not all([chain, llm, graph]):
        raise HTTPException(status_code=503, detail="Services not fully initialized.")

    routing = rephrase_and_route(request.query, request.history, llm)
    
    if not routing.allowed:
        return QueryResponse(response="This system is designed to answer questions related to the provided dataset only.")
    
    try:
        graph.refresh_schema()
        # Thread pool prevents the API from hanging indefinitely on bad queries
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(chain.invoke, {"query": routing.standalone_query})
            result = future.result(timeout=settings.timeout_seconds) 
            
        return QueryResponse(response=result['result'])
    
    except concurrent.futures.TimeoutError:
        logger.error(f"Query timed out after {settings.timeout_seconds}s: {routing.standalone_query}")
        raise HTTPException(status_code=408, detail="The database query took too long to process. The dataset might need indexing.")
    except Exception as e:
        logger.error(f"Chain execution error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while processing your request against the graph.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)