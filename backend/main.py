# import os
# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# from typing import List, Dict
# from dotenv import load_dotenv
# from langchain_community.graphs import Neo4jGraph
# from langchain_groq import ChatGroq
# from langchain.chains import GraphCypherQAChain
# from neo4j import GraphDatabase
# from langchain.prompts import PromptTemplate

# load_dotenv()

# app = FastAPI(title="Graph-Based Data Modeling and Query Engine")

# NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
# NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
# NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# def get_default_database(uri, user, pw):
#     driver = GraphDatabase.driver(uri, auth=(user, pw))
#     with driver.session() as session:
#         res = session.run("CALL db.info() YIELD name RETURN name")
#         for r in res:
#             return r["name"]
#     return "neo4j"

# NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")
# if not NEO4J_DATABASE:
#     try:
#         NEO4J_DATABASE = get_default_database(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
#     except Exception:
#         NEO4J_DATABASE = "neo4j"

# graph = Neo4jGraph(
#     url=NEO4J_URI, 
#     username=NEO4J_USERNAME, 
#     password=NEO4J_PASSWORD, 
#     database=NEO4J_DATABASE
# )

# llm = ChatGroq(
#     groq_api_key=GROQ_API_KEY,
#     model_name="llama-3.3-70b-versatile",
#     temperature=0
# )

# from langchain.prompts import PromptTemplate

# # CYPHER_GENERATION_TEMPLATE = """Task: Generate a Cypher statement to query a graph database.

# # CRITICAL INSTRUCTIONS:
# # 1. Use ONLY the provided relationship types and properties in the schema. Do not guess or hallucinate relationships.
# # 2. NEVER use the variable 'p' to define a path. NEVER write `MATCH p=(...)`. If you must trace a path, use `MATCH flow=(...)`.
# # 3. If tracing a full flow, add `LIMIT 3` to the end of your query so you don't overwhelm the response context.
# # 4. To find "broken" or "incomplete" flows (e.g., delivered but not billed), use the WHERE NOT EXISTS pattern. Example: `MATCH (so:SalesOrder) WHERE NOT (so)-[]-(:BillingDocument) RETURN so LIMIT 5`
# # 5. If a query returns empty results, it means there are no records matching that criteria. Respond clearly: "Based on the data, there are no records of that type."

# # Schema:
# # {schema}

# # Note: Do not include any explanations or apologies in your Cypher output. Return ONLY the valid Cypher statement.

# # The question is:
# # {question}
# # """

# # CYPHER_GENERATION_TEMPLATE = """Task: Generate a Cypher statement to query a graph database.

# # CRITICAL INSTRUCTIONS (FAILURE TO FOLLOW WILL BREAK THE SYSTEM):
# # 1. Use ONLY the provided relationship types and properties in the schema.
# # 2. NEVER use the variable 'p' for a path. Use `MATCH path=(...)`.
# # 3. NEVER return entire nodes (e.g., `RETURN n`). ALWAYS return specific, readable properties (e.g., `RETURN n.order_id`).
# # 4. IF USING UNION: All subqueries MUST return the EXACT SAME column aliases. Example: `RETURN n.id AS document_id, 'No Billing' AS issue UNION RETURN m.id AS document_id, 'No Delivery' AS issue`.
# # 5. To find broken flows, use WHERE NOT EXISTS. Example: `MATCH (so:SalesOrder)<-[:DELIVERS]-(od:OutboundDelivery) WHERE NOT EXISTS {{ (od)-[:BILLS]->(:BillingDocument) }} RETURN so.order_id AS id, 'Delivered not billed' AS status LIMIT 5`.
# # 6. If the user asks to trace a generic flow but does not provide an ID, retrieve any complete path and return its IDs. Example: `MATCH (so:SalesOrder)-...-(je:JournalEntry) RETURN so.order_id, od.delivery_id, bd.document_id, je.entry_id LIMIT 1`.
# # 7. ALWAYS append `LIMIT 5` to any query returning multiple entities to prevent data overload.

# # Schema:
# # {schema}

# # Return ONLY the valid Cypher statement. Do not include explanations.

# # The question is:
# # {question}
# # """

# # QA_PROMPT = """You are a helpful data analyst assisting with an Order-to-Cash graph database.

# # Context from database:
# # {context}

# # Question: {question}

# # Instructions:
# # 1. Translate the raw database context into a clear, natural language response.
# # 2. If the user asks for a general example (e.g., "Trace the full flow of a given billing document") without specifying an ID, the context will provide a sample flow. Use that sample to explain the flow naturally.
# # 3. If the context is empty ([]), respond EXACTLY with: "Based on the available data, there are no records matching that query."
# # 4. Do not say "Based on the context" or "According to the database." Just present the information directly.

# # Answer:"""

# CYPHER_GENERATION_TEMPLATE = """Task: Generate a Cypher statement to query a graph database.

# CRITICAL INSTRUCTIONS (FAILURE TO FOLLOW WILL BREAK THE SYSTEM):
# 1. Use ONLY the provided relationship types and properties in the schema.
# 2. NEVER use the variable 'p' for a path. Use `MATCH path=(...)`.
# 3. NEVER return entire nodes (e.g., `RETURN n`). ALWAYS return specific, readable properties (e.g., `RETURN n.order_id`).
# 4. IF USING UNION: All subqueries MUST return the EXACT SAME column aliases. Example: `RETURN n.id AS document_id, 'No Billing' AS issue UNION RETURN m.id AS document_id, 'No Delivery' AS issue`.
# 5. To find broken flows, use WHERE NOT EXISTS. Example: `MATCH (so:SalesOrder)<-[:DELIVERS]-(od:OutboundDelivery) WHERE NOT EXISTS {{ (od)-[:BILLS]->(:BillingDocument) }} RETURN so.order_id AS id, 'Delivered not billed' AS status LIMIT 5`.
# 6. If the user asks to trace a generic flow but does not provide an ID, retrieve any complete path and return its IDs. Example: `MATCH (so:SalesOrder)-...-(je:JournalEntry) RETURN so.order_id, od.delivery_id, bd.document_id, je.entry_id LIMIT 1`.
# 7. ALWAYS append `LIMIT 5` to any query returning multiple entities to prevent data overload.

# Schema:
# {schema}

# Return ONLY the valid Cypher statement. Do not include explanations.

# The question is:
# {question}
# """

# QA_PROMPT = """You are a helpful data analyst assisting with an Order-to-Cash graph database.

# Context from database:
# {context}

# Question: {question}

# Instructions:
# 1. Translate the raw database context into a clear, natural language response.
# 2. If the user asks for a general example (e.g., "Trace the full flow of a given billing document") without specifying an ID, the context will provide a sample flow. Use that sample to explain the flow naturally.
# 3. If the context is empty ([]), respond EXACTLY with: "Based on the available data, there are no records matching that query."
# 4. Do not say "Based on the context" or "According to the database." Just present the information directly.

# Answer:"""

# CYPHER_GENERATION_PROMPT = PromptTemplate(
#     input_variables=["schema", "question"], template=CYPHER_GENERATION_TEMPLATE
# )

# QA_PROMPT_TEMPLATE = PromptTemplate(
#     input_variables=["context", "question"], template=QA_PROMPT
# )

# # Enhanced chain with return_direct=False to ensure QA generation works
# chain = GraphCypherQAChain.from_llm(
#     cypher_llm=llm,
#     qa_llm=llm,
#     graph=graph,
#     verbose=True,
#     cypher_prompt=CYPHER_GENERATION_PROMPT,
#     qa_prompt=QA_PROMPT_TEMPLATE,
#     allow_dangerous_requests=True,
#     validate_cypher=True,
#     return_intermediate_steps=True,
#     top_k=10
# )

# class QueryRequest(BaseModel):
#     query: str
#     history: List[Dict[str, str]] = []

# class RouterOutput(BaseModel):
#     allowed: bool
#     standalone_query: str

# def rephrase_and_route(query: str, history: List[Dict[str, str]]) -> RouterOutput:
#     formatted_history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-4:]]) if history else ""
#     prompt = f"""You are an intelligent router for a Supply Chain Order-to-Cash Graph database AI.
# Given the conversation history and the latest user query:
# 1. Determine if the query is allowed (related to supply chain, billing, orders, customers, deliveries, products).
# 2. If allowed, rewrite the query to be a fully standalone question resolving pronouns (e.g. "this", "he") based on the history. If no history, leave query as is.

# Respond ONLY with a valid JSON object matching this schema:
# {{
#   "allowed": true or false,
#   "standalone_query": "string"
# }}

# History:
# {formatted_history}

# Latest Query: {query}
# JSON Output:"""
    
#     import json
#     response = llm.invoke(prompt)
#     try:
#         content = response.content.replace('```json', '').replace('```', '').strip()
#         data = json.loads(content)
#         return RouterOutput(allowed=data.get("allowed", True), standalone_query=data.get("standalone_query", query))
#     except Exception:
#         # Fallback to true if LLM formatting glitch
#         return RouterOutput(allowed=True, standalone_query=query)

# import concurrent.futures

# @app.post("/chat")
# def chat_endpoint(request: QueryRequest):
#     routing = rephrase_and_route(request.query, request.history)
    
#     if not routing.allowed:
#         return {"response": "This system is designed to answer questions related to the provided dataset only."}
    
#     try:
#         graph.refresh_schema()
#         # Prevent indefinite hanging when Cypher validation gets stuck in a retry loop
#         with concurrent.futures.ThreadPoolExecutor() as executor:
#             future = executor.submit(chain.invoke, {"query": routing.standalone_query})
#             result = future.result(timeout=45) 
            
#         return {"response": result['result']}
#     except concurrent.futures.TimeoutError:
#         return {"response": "The query was too complex to translate into Cypher before timing out. Please rephrase."}
#     except Exception as e:
#         return {"response": f"An error occurred: {str(e)}"}




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

# Highly optimized Cypher generation prompt
CYPHER_GENERATION_TEMPLATE = """Task: Generate a Cypher statement to query a graph database.

CRITICAL INSTRUCTIONS (FAILURE TO FOLLOW WILL BREAK THE SYSTEM):
1. Use ONLY the provided relationship types and properties in the schema.
2. NEVER use the variable 'p' for a path. Use `MATCH path=(...)`.
3. NEVER return entire nodes (e.g., `RETURN n`). ALWAYS return specific properties (e.g., `RETURN n.order_id`).
4. IF TRACING A FLOW (without a specific ID): Use a variable-length path to find a random sample. Example: `MATCH path=(so:SalesOrder)-[*1..4]-(je:JournalEntry) RETURN [n IN nodes(path) | coalesce(n.order_id, n.document_id, n.delivery_id)] AS flow_ids LIMIT 1`.
5. IF FINDING BROKEN FLOWS: Keep it incredibly simple to prevent database timeouts. Example: `MATCH (od:OutboundDelivery) WHERE NOT (od)--(:BillingDocument) RETURN od.delivery_id AS delivered_not_billed LIMIT 5`. Do NOT use complex UNIONs.
6. IF FINDING MAX/HIGHEST: Use aggregations. Example: `MATCH (p:Product)<-[:CONTAINS]-(...)-[:BILLS]->(bd) WITH p, count(bd) as c RETURN p.product_id, c ORDER BY c DESC LIMIT 1`.
7. ALWAYS append `LIMIT 5` to any query returning multiple entities to prevent data overload.

Schema:
{schema}

Return ONLY the valid Cypher statement. Do not include explanations.

The question is:
{question}
"""

# Relaxed QA prompt to handle missing data and generic samples gracefully
QA_PROMPT = """You are a helpful data analyst assisting with an Order-to-Cash graph database.

Context from database:
{context}

Question: {question}

Instructions:
1. Translate the raw database context into a clear, natural language response.
2. If the user asks for a general example (e.g., "Trace the full flow of a given billing document") without specifying an ID, the context will provide a sample flow. Use that sample to explain the flow naturally.
3. If the context is empty ([]), respond EXACTLY with: "Based on the available data, there are no records matching that query."
4. Do not say "Based on the context" or "According to the database." Just present the information directly.

Answer:"""

CYPHER_GENERATION_PROMPT = PromptTemplate(
    input_variables=["schema", "question"], template=CYPHER_GENERATION_TEMPLATE
)

QA_PROMPT_TEMPLATE = PromptTemplate(
    input_variables=["context", "question"], template=QA_PROMPT
)

# Core LangChain QA Chain
chain = GraphCypherQAChain.from_llm(
    cypher_llm=llm,
    qa_llm=llm,
    graph=graph,
    verbose=True,
    cypher_prompt=CYPHER_GENERATION_PROMPT,
    qa_prompt=QA_PROMPT_TEMPLATE,
    allow_dangerous_requests=True,
    validate_cypher=True,
    return_intermediate_steps=True,
    top_k=10  # Strict limit to prevent LLM context window crashes
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
2. If allowed, rewrite the query to be a fully standalone question resolving pronouns (e.g. "this", "he") based on the history. If no history, leave query as is.

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
        # Thread pool with strict timeout to prevent infinite "researching" spinners
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(chain.invoke, {"query": routing.standalone_query})
            result = future.result(timeout=45) 
            
        return {"response": result['result']}
    except concurrent.futures.TimeoutError:
        return {"response": "The query was too complex to translate into Cypher before timing out. Please rephrase your question."}
    except Exception as e:
        return {"response": f"An error occurred: {str(e)}"}