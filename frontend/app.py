import os
import re
import logging
import requests
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network
from neo4j import GraphDatabase, exceptions as neo4j_exceptions
from dotenv import load_dotenv

# Setup & Configuration
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FASTAPI_URL = os.getenv("FASTAPI_URL", "https://nexus-graph-engine-1.onrender.com/chat")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "password")

st.set_page_config(page_title="Nexus O2C Graph Engine", layout="wide", initial_sidebar_state="collapsed")

def inject_custom_css():
    """Injects production-grade UI overrides."""
    st.markdown("""
    <style>
        .stApp { background-color: #ffffff; }
        div[data-testid="stVerticalBlock"] > div:first-child { padding-top: 0rem; }
        h1, h2, h3, h4, h5, h6, span, label, .stMarkdown p { color: #1f2937 !important; }
        .stChatMessage p { color: #1f2937 !important; } 
        hr { border-bottom-color: #e5e7eb !important; }
        .stAlert { background-color: #fee2e2; color: #991b1b; } /* Custom error alert */
    </style>
    """, unsafe_allow_html=True)

# Graph Logic
@st.cache_resource
def get_neo4j_driver():
    """Creates and caches a Neo4j driver connection."""
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
        driver.verify_connectivity()
        return driver
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        st.error("Database connection failed. Please ensure Neo4j is running.")
        st.stop()

def build_node_tooltip(n_label: str, n_props: dict) -> str:
    """Formats a clean, robust tooltip for PyVis nodes."""
    tooltip = f"[{n_label}]\n" + "-"*15 + "\n"
    for k, v in n_props.items():
        tooltip += f"{k}: {v}\n"
    return tooltip

def get_node_styling(n_label: str) -> str:
    """Returns standard border colors based on node type."""
    color_map = {
        "JournalEntry": "#ff9999",
        "BillingDocument": "#ffb366",
        "SalesOrder": "#99ff99",
        "OutboundDelivery": "#ffff99",
        "Product": "#d9b3ff",
        "Customer": "#cce5ff"
    }
    return color_map.get(n_label, "#a5d6f1")

def generate_graph_html(extracted_ids: tuple) -> str:
    """Queries Neo4j and generates an HTML interactive network graph."""
    net = Network(height="800px", width="100%", bgcolor="#ffffff", font_color="#000000", directed=True)
    driver = get_neo4j_driver()
    
    query = """
    MATCH (n)-[r]-(m)
    WHERE size($ids) = 0 
       OR any(k IN keys(n) WHERE toString(n[k]) IN $ids) 
       OR any(k IN keys(m) WHERE toString(m[k]) IN $ids)
    RETURN id(n) AS source_id, labels(n)[0] AS source_label, n AS source_props,
           id(m) AS target_id, labels(m)[0] AS target_label, m AS target_props,
           type(r) AS rel_type
    LIMIT 300
    """
    
    try:
        with driver.session() as session:
            results = session.run(query, ids=list(extracted_ids))
            nodes_added = set()
            
            for record in results:
                src_id, tgt_id = record["source_id"], record["target_id"]
                
                # Abstracted node addition logic
                for node_prefix in [("source", src_id), ("target", tgt_id)]:
                    prefix, n_id = node_prefix
                    if n_id not in nodes_added:
                        n_label = record[f"{prefix}_label"]
                        n_props = dict(record[f"{prefix}_props"])
                        
                        # Find primary identifier for display
                        display_name = n_label 
                        for key in ["customer_name", "product_id", "order_id", "document_id", "id", "Customer", "Product"]:
                            if key in n_props:
                                display_name = str(n_props[key])
                                break 
                        
                        net.add_node(
                            n_id, 
                            label=display_name, 
                            title=build_node_tooltip(n_label, n_props), 
                            color={"background": "#ffffff", "border": get_node_styling(n_label)},
                            borderWidth=2, 
                            size=20, 
                            font={"color": "#1f2937", "size": 12}
                        )
                        nodes_added.add(n_id)

                net.add_edge(src_id, tgt_id, title=record["rel_type"], color="#bde0fe", width=1)
                
    except neo4j_exceptions.Neo4jError as e:
        logger.error(f"Neo4j Query Error: {e}")
        return f"<div style='color:red; padding:20px;'>Failed to render graph data: {str(e)}</div>"

    net.set_options("""
    var options = {
      "nodes": { "shape": "dot", "font": { "size": 14, "color": "#1f2937", "face": "sans-serif" } },
      "edges": { "color": { "color": "#bde0fe", "highlight": "#3b82f6" }, "smooth": { "type": "continuous" } },
      "interaction": { "hover": true, "tooltipDelay": 100, "zoomView": true },
      "physics": {
        "forceAtlas2Based": { "gravitationalConstant": -50, "centralGravity": 0.005, "springLength": 200 },
        "solver": "forceAtlas2Based"
      }
    }
    """)
    return net.generate_html()

# Main UI Execution
def main():
    inject_custom_css()
    
    # Initialize Session State
    if "messages" not in st.session_state:
        st.session_state["messages"] = [
            {"role": "assistant", "content": "Hi! I can help you analyze the **Order to Cash** process."}
        ]

    col1, col2 = st.columns([2.5, 1], gap="large")

    with col1:
        st.markdown("### 🗺️ Mapping / Order to Cash")
        graph_placeholder = st.empty()

    with col2:
        st.markdown("### Chat with Graph\n**Order to Cash**\n---")
        chat_container = st.container(height=650)
        
        # Render history
        with chat_container:
            for msg in st.session_state.messages:
                avatar = "🤖" if msg["role"] == "assistant" else "👤"
                with st.chat_message(msg["role"], avatar=avatar):
                    st.markdown(msg["content"])

        # Chat Input Handeling
        if prompt := st.chat_input("Analyze anything..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with chat_container:
                with st.chat_message("user", avatar="👤"):
                    st.markdown(prompt)

                with st.chat_message("assistant", avatar="🤖"):
                    with st.spinner("Nexus O2C Graph Engine is researching..."):
                        history_payload = [
                            {"role": m["role"], "content": m["content"]} 
                            for m in st.session_state.messages[:-1] 
                            if m["role"] in ["user", "assistant"]
                        ]
                        
                        try:
                            # Using proper status code checks
                            response = requests.post(
                                FASTAPI_URL, 
                                json={"query": prompt, "history": history_payload}, 
                                timeout=60
                            )
                            
                            if response.status_code == 200:
                                answer = response.json().get("response", "No answer found.")
                            elif response.status_code == 408:
                                answer = "Request Timeout: The database query was too complex. Try a more specific question."
                            else:
                                detail = response.json().get('detail', 'Unknown backend error')
                                answer = f"Server Error ({response.status_code}): {detail}"
                                
                        except requests.exceptions.Timeout:
                            answer = "Connection Timeout: The backend took too long to respond."
                        except requests.exceptions.ConnectionError:
                            answer = "Connection Error: Ensure the FastAPI backend is running."
                        except Exception as e:
                            answer = f"Unexpected Error: {str(e)}"
                    
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})


    last_assistant_msg = ""
    for msg in reversed(st.session_state.messages):
        if msg["role"] == "assistant":
            last_assistant_msg = msg["content"]
            break


    extracted_ids = tuple(re.findall(r'\b[A-Z0-9]{5,25}\b', last_assistant_msg)) if last_assistant_msg else tuple()
    
    with graph_placeholder.container():
        with st.spinner("Rendering graph topology..."):
            graph_html = generate_graph_html(extracted_ids)
            components.html(graph_html, height=820, scrolling=False)

if __name__ == "__main__":
    main()