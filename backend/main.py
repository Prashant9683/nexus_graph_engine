import os
import concurrent.futures
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from dotenv import load_dotenv
from langchain_community.graphs import Neo4jGraph
from langchain_groq import ChatGroq
from langchain.chains import GraphCypherQAChain
from neo4j import GraphDatabase
from langchain.prompts import PromptTemplate

load_dotenv()

app = FastAPI(title="Graph-Based Data Modeling and Query Engine")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def get_default_database(uri, user, pw):
    driver = GraphDatabase.driver(uri, auth=(user, pw))
    with driver.session() as session:
        res = session.run("CALL db.info() YIELD name RETURN name")
        for r in res:
            return r["name"]
    return "neo4j"

NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")
if not NEO4J_DATABASE:
    try:
        NEO4J_DATABASE = get_default_database(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
    except Exception:
        NEO4J_DATABASE = "neo4j"

graph = Neo4jGraph(
    url=NEO4J_URI, 
    username=NEO4J_USERNAME, 
    password=NEO4J_PASSWORD, 
    database=NEO4J_DATABASE
)

llm = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model_name="llama-3.3-70b-versatile",
    temperature=0
)

# --- THE BULLETPROOF CYPHER PROMPT ---
# CYPHER_GENERATION_TEMPLATE = """Task: Generate a Cypher statement to query a graph database.

# CRITICAL INSTRUCTIONS (FAILURE TO FOLLOW WILL BREAK THE SYSTEM):
# 1. Schema Compliance: Use ONLY the exact relationship types and properties in the provided schema.
# 2. Undirected Paths: When tracing flows, omit arrows to avoid directionality errors. Use `()-[]-()` instead of `()->()`.
# 3. Anchor Trace Queries: To prevent database timeouts on large graphs, ALWAYS anchor variable-length paths to a single node first.
#    CORRECT Trace Example: `MATCH (so:SalesOrder) WITH so LIMIT 1 MATCH path=(so)-[*1..5]-(je:JournalEntry) RETURN [n IN nodes(path) | coalesce(n.id, n.order_id, n.document_id, n.delivery_id, n.entry_id)] AS flow LIMIT 1`
# 4. Broken Flows: Use the highly optimized `WHERE NOT EXISTS` syntax. Do not use UNIONs.
#    CORRECT Broken Example: `MATCH (od:OutboundDelivery) WHERE NOT EXISTS {{ (od)-[]-(:BillingDocument) }} RETURN coalesce(od.id, od.delivery_id) AS delivered_not_billed LIMIT 5`
# 5. Return Limits: NEVER return entire nodes (`RETURN n`). Return string/int properties. ALWAYS append `LIMIT 5`.
# 6. Aggregations: For "highest/most", use `ORDER BY count DESC LIMIT 1`.

# Schema:
# {schema}

# Return ONLY the valid Cypher statement. Do not include explanations.

# The question is:
# {question}
# """

CYPHER_GENERATION_TEMPLATE = """Task: Generate a Cypher statement to query a graph database.

CRITICAL INSTRUCTIONS (FAILURE TO FOLLOW WILL BREAK THE SYSTEM):
1. Schema Compliance: Use ONLY the exact relationship types and properties in the schema.
2. Undirected Paths: Omit arrows. Use `()-[]-()` instead of `()->()`.
3. Broken Flows: Use `WHERE NOT EXISTS`. Example: `MATCH (od:OutboundDelivery) WHERE NOT EXISTS {{ (od)-[]-(:BillingDocument) }} RETURN coalesce(od.id, od.delivery_id) AS delivered_not_billed LIMIT 5`
4. Trace Flow (Sample): If no ID is provided, find ONE successful path. Do NOT anchor to a random node first, as it might be a broken flow! 
   Example: `MATCH path=(:SalesOrder)-[*1..4]-(:JournalEntry) RETURN [n IN nodes(path) | coalesce(n.order_id, n.document_id, n.delivery_id, n.entry_id)] AS flow LIMIT 1`
5. Max/Highest & Ties: ALWAYS use `LIMIT 5` instead of `LIMIT 1` when ordering by count. This ensures you catch ties for 1st place. Example: `... RETURN p.product_id, c ORDER BY c DESC LIMIT 5`
6. Return Limits: NEVER return entire nodes (`RETURN n`). Return properties.

Schema:
{schema}

Return ONLY the valid Cypher statement. Do not include explanations.

The question is:
{question}
"""

QA_PROMPT = """You are a helpful data analyst assisting with an Order-to-Cash graph database.

Context from database:
{context}

Question: {question}

Instructions:
1. Translate the raw database context into a clear, natural language response.
2. If the user asks for a general example (e.g., "Trace the full flow of a given billing document") without specifying an ID, the context will provide a sample flow array. Format that array into a readable sequence (e.g., "Here is a sample flow: Order X -> Delivery Y -> Billing Z").
3. If the context is empty ([]), respond EXACTLY with: "Based on the available data, there are no records matching that criteria."
4. Do not say "Based on the context". Just present the information.

Answer:"""

CYPHER_GENERATION_PROMPT = PromptTemplate(
    input_variables=["schema", "question"], template=CYPHER_GENERATION_TEMPLATE
)

QA_PROMPT_TEMPLATE = PromptTemplate(
    input_variables=["context", "question"], template=QA_PROMPT
)

chain = GraphCypherQAChain.from_llm(
    cypher_llm=llm,
    qa_llm=llm,
    graph=graph,
    verbose=True, # Leave this True to monitor generated queries in the terminal
    cypher_prompt=CYPHER_GENERATION_PROMPT,
    qa_prompt=QA_PROMPT_TEMPLATE,
    allow_dangerous_requests=True,
    validate_cypher=True,
    return_intermediate_steps=True,
    top_k=10
)

class QueryRequest(BaseModel):
    query: str
    history: List[Dict[str, str]] = []

class RouterOutput(BaseModel):
    allowed: bool
    standalone_query: str

def rephrase_and_route(query: str, history: List[Dict[str, str]]) -> RouterOutput:
    formatted_history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-4:]]) if history else ""
    prompt = f"""You are an intelligent router for a Supply Chain Order-to-Cash Graph database AI.
Given the conversation history and the latest user query:
1. Determine if the query is allowed (related to supply chain, billing, orders, customers, deliveries, products).
2. If allowed, rewrite the query to be a fully standalone question resolving pronouns. If no history, leave query as is.

Respond ONLY with a valid JSON object matching this schema:
{{
  "allowed": true or false,
  "standalone_query": "string"
}}

History:
{formatted_history}

Latest Query: {query}
JSON Output:"""
    
    import json
    response = llm.invoke(prompt)
    try:
        content = response.content.replace('```json', '').replace('```', '').strip()
        data = json.loads(content)
        return RouterOutput(allowed=data.get("allowed", True), standalone_query=data.get("standalone_query", query))
    except Exception:
        return RouterOutput(allowed=True, standalone_query=query)

@app.post("/chat")
def chat_endpoint(request: QueryRequest):
    routing = rephrase_and_route(request.query, request.history)
    
    if not routing.allowed:
        return {"response": "This system is designed to answer questions related to the provided dataset only."}
    
    try:
        graph.refresh_schema()
        # Extended backend timeout to 55 seconds to gracefully handle Groq's API latency
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(chain.invoke, {"query": routing.standalone_query})
            result = future.result(timeout=55) 
            
        return {"response": result['result']}
    except concurrent.futures.TimeoutError:
        return {"response": "The query took too long to process. The database might need indexes on the ID fields."}
    except Exception as e:
        return {"response": f"An error occurred: {str(e)}"}