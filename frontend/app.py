# import streamlit as st
# import requests
# import streamlit.components.v1 as components
# from pyvis.network import Network
# import os
# from neo4j import GraphDatabase
# from dotenv import load_dotenv
# import re

# load_dotenv()

# FASTAPI_URL = "http://localhost:8000/chat"

# st.set_page_config(page_title="Nexus O2C Graph Engine", layout="wide", initial_sidebar_state="collapsed")

# st.markdown("""
# <style>
#     .stApp { background-color: #ffffff; }
#     div[data-testid="stVerticalBlock"] > div:first-child { padding-top: 0rem; }
    
#     /* Force headers and main text to be dark */
#     h1, h2, h3, h4, h5, h6, span, label, .stMarkdown p { color: #1f2937 !important; }
    
#     /* Ensure chat text is dark */
#     .stChatMessage p { color: #1f2937 !important; } 
    
#     /* Make the horizontal line darker so it's visible */
#     hr { border-bottom-color: #e5e7eb !important; }
# </style>
# """, unsafe_allow_html=True)

# @st.cache_resource
# def get_neo4j_driver():
#     URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
#     USER = os.getenv("NEO4J_USERNAME", "neo4j")
#     PASS = os.getenv("NEO4J_PASSWORD", "password")
#     return GraphDatabase.driver(URI, auth=(USER, PASS))

# @st.cache_data
# def generate_graph_html(extracted_ids_tuple: tuple):
#     net = Network(height="800px", width="100%", bgcolor="#ffffff", font_color="#000000", directed=True)
#     driver = get_neo4j_driver()
    
#     with driver.session() as session:
#         # Dynamic Cypher: If IDs exist, pull their 1-hop neighborhood. Else, pull a limited overview.
#         query = """
#         MATCH (n)-[r]-(m)
#         WHERE size($ids) = 0 
#            OR any(k IN keys(n) WHERE toString(n[k]) IN $ids) 
#            OR any(k IN keys(m) WHERE toString(m[k]) IN $ids)
#         RETURN id(n) AS source_id, labels(n)[0] AS source_label, n AS source_props,
#                id(m) AS target_id, labels(m)[0] AS target_label, m AS target_props,
#                type(r) AS rel_type
#         LIMIT 300
#         """
#         results = session.run(query, ids=list(extracted_ids_tuple))
        
#         nodes_added = set()
        
#         for record in results:
#             src_id, src_label, src_props = record["source_id"], record["source_label"], dict(record["source_props"])
#             tgt_id, tgt_label, tgt_props = record["target_id"], record["target_label"], dict(record["target_props"])
#             rel_type = record["rel_type"]
            

#             def add_node_to_net(n_id, n_label, n_props):
#                 if n_id in nodes_added: return
                
#                 border_color = "#a5d6f1"
#                 if n_label == "JournalEntry": border_color = "#ff9999" 
#                 elif n_label == "BillingDocument": border_color = "#ffb366" 
#                 elif n_label == "SalesOrder": border_color = "#99ff99" 
#                 elif n_label == "OutboundDelivery": border_color = "#ffff99"
#                 elif n_label == "Product": border_color = "#d9b3ff"
#                 elif n_label == "Customer": border_color = "#cce5ff" 
                
#                 # --- NEW: Extract a meaningful label to display on the node ---
#                 display_name = n_label # Default to the type of node
#                 for key in ["customer_name", "product_id", "order_id", "document_id", "id", "Customer", "Product"]:
#                     if key in n_props:
#                         display_name = str(n_props[key])
#                         break # Stop at the first good identifier we find
                
#                 # --- NEW: Robust Plain Text Tooltip ---
#                 tooltip_text = f"[{n_label}]\n" + "-"*15 + "\n"
#                 for k, v in n_props.items():
#                     tooltip_text += f"{k}: {v}\n"
                    
#                 # Note: label=display_name instead of label=""
#                 net.add_node(n_id, label=display_name, title=tooltip_text, 
#                              color={"background": "#ffffff", "border": border_color},
#                              borderWidth=2, size=20, 
#                              font={"color": "#1f2937", "size": 12}) # Make text dark and readable
#                 nodes_added.add(n_id)
#             add_node_to_net(src_id, src_label, src_props)
#             add_node_to_net(tgt_id, tgt_label, tgt_props)
            
#             # Add the edge connecting them
#             net.add_edge(src_id, tgt_id, title=rel_type, color="#bde0fe", width=1)
            
#     net.set_options("""
#     var options = {
#       "nodes": { "shape": "dot" },
#       "interaction": { "hover": true, "tooltipDelay": 200 },
#       "physics": {
#         "forceAtlas2Based": { "gravitationalConstant": -40, "centralGravity": 0.005, "springLength": 200 },
#         "solver": "forceAtlas2Based"
#       }
#     }
#     """)
#     return net.generate_html()

# last_assistant_msg = ""
# if "messages" in st.session_state:
#     for msg in reversed(st.session_state.messages):
#         if msg["role"] == "assistant":
#             last_assistant_msg = msg["content"]
#             break

# extracted_ids = tuple(re.findall(r'\b[A-Z0-9]{8,20}\b', last_assistant_msg)) if last_assistant_msg else tuple()

# col1, col2 = st.columns([2.5, 1], gap="large")

# with col1:
#     st.markdown("### 🗺️ Mapping / Order to Cash")
#     with st.spinner("Analyzing graph topology..."):
#         graph_html = generate_graph_html(extracted_ids)
#         components.html(graph_html, height=820, scrolling=False)

# with col2:
#     st.markdown("### Chat with Graph\n**Order to Cash**\n---")
    
#     if "messages" not in st.session_state:
#         st.session_state["messages"] = [
#             {"role": "assistant", "content": "Hi! I can help you analyze the **Order to Cash** process."}
#         ]

#     chat_container = st.container(height=650)
    
#     with chat_container:
#         for msg in st.session_state.messages:
#             with st.chat_message(msg["role"], avatar="🤖" if msg["role"] == "assistant" else "👤"):
#                 st.markdown(msg["content"])

#     if prompt := st.chat_input("Analyze anything..."):
#         st.session_state.messages.append({"role": "user", "content": prompt})
#         with chat_container:
#             with st.chat_message("user", avatar="👤"):
#                 st.markdown(prompt)

#             with st.chat_message("assistant", avatar="🤖"):
#                 with st.spinner("Dodge AI Graph Agent is researching..."):
#                     try:
#                         # Extract the exact history excluding the system ones and the current prompt
#                         history_payload = [
#                             {"role": m["role"], "content": m["content"]} 
#                             for m in st.session_state.messages[:-1] 
#                             if m["role"] in ["user", "assistant"]
#                         ]
                        
#                         response = requests.post(
#                             FASTAPI_URL, 
#                             json={"query": prompt, "history": history_payload},
#                             timeout=60
#                         )
#                         response.raise_for_status()
#                         answer = response.json().get("response", "No answer found.")
#                     except requests.exceptions.Timeout:
#                         answer = "The query took too long to process. Could you try asking a more specific question?"
#                     except Exception as e:
#                         answer = f"Error connecting to backend: {str(e)}"
                
#                 st.markdown(answer)
#                 st.session_state.messages.append({"role": "assistant", "content": answer})


import streamlit as st
import requests
import streamlit.components.v1 as components
from pyvis.network import Network
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
import re

load_dotenv()

FASTAPI_URL = "http://localhost:8000/chat"

st.set_page_config(page_title="Nexus O2C Graph Engine", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS for light theme and visible dark text
st.markdown("""
<style>
    .stApp { background-color: #ffffff; }
    div[data-testid="stVerticalBlock"] > div:first-child { padding-top: 0rem; }
    h1, h2, h3, h4, h5, h6, span, label, .stMarkdown p { color: #1f2937 !important; }
    .stChatMessage p { color: #1f2937 !important; } 
    hr { border-bottom-color: #e5e7eb !important; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_neo4j_driver():
    URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    USER = os.getenv("NEO4J_USERNAME", "neo4j")
    PASS = os.getenv("NEO4J_PASSWORD", "password")
    return GraphDatabase.driver(URI, auth=(USER, PASS))

def generate_graph_html(extracted_ids_tuple: tuple):
    net = Network(height="800px", width="100%", bgcolor="#ffffff", font_color="#000000", directed=True)
    driver = get_neo4j_driver()
    
    with driver.session() as session:
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
        results = session.run(query, ids=list(extracted_ids_tuple))
        nodes_added = set()
        
        for record in results:
            src_id, src_label, src_props = record["source_id"], record["source_label"], dict(record["source_props"])
            tgt_id, tgt_label, tgt_props = record["target_id"], record["target_label"], dict(record["target_props"])
            rel_type = record["rel_type"]
            
            def add_node_to_net(n_id, n_label, n_props):
                if n_id in nodes_added: return
                
                border_color = "#a5d6f1"
                if n_label == "JournalEntry": border_color = "#ff9999" 
                elif n_label == "BillingDocument": border_color = "#ffb366" 
                elif n_label == "SalesOrder": border_color = "#99ff99" 
                elif n_label == "OutboundDelivery": border_color = "#ffff99"
                elif n_label == "Product": border_color = "#d9b3ff"
                elif n_label == "Customer": border_color = "#cce5ff" 
                
                display_name = n_label 
                for key in ["customer_name", "product_id", "order_id", "document_id", "id", "Customer", "Product"]:
                    if key in n_props:
                        display_name = str(n_props[key])
                        break 
                
                tooltip_text = f"[{n_label}]\n" + "-"*15 + "\n"
                for k, v in n_props.items():
                    tooltip_text += f"{k}: {v}\n"
                    
                net.add_node(n_id, label=display_name, title=tooltip_text, 
                             color={"background": "#ffffff", "border": border_color},
                             borderWidth=2, size=20, 
                             font={"color": "#1f2937", "size": 12}) 
                nodes_added.add(n_id)

            add_node_to_net(src_id, src_label, src_props)
            add_node_to_net(tgt_id, tgt_label, tgt_props)
            net.add_edge(src_id, tgt_id, title=rel_type, color="#bde0fe", width=1)
            
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


col1, col2 = st.columns([2.5, 1], gap="large")

with col1:
    st.markdown("### 🗺️ Mapping / Order to Cash")
    # Empty placeholder allowing graph to render AFTER the chat updates
    graph_placeholder = st.empty()

with col2:
    st.markdown("### Chat with Graph\n**Order to Cash**\n---")
    
    if "messages" not in st.session_state:
        st.session_state["messages"] = [
            {"role": "assistant", "content": "Hi! I can help you analyze the **Order to Cash** process."}
        ]

    chat_container = st.container(height=650)
    
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"], avatar="🤖" if msg["role"] == "assistant" else "👤"):
                st.markdown(msg["content"])

    if prompt := st.chat_input("Analyze anything..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)

            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Nexus O2C Graph Engine is researching..."):
                    try:
                        history_payload = [
                            {"role": m["role"], "content": m["content"]} 
                            for m in st.session_state.messages[:-1] 
                            if m["role"] in ["user", "assistant"]
                        ]
                        
                        response = requests.post(FASTAPI_URL, json={"query": prompt, "history": history_payload}, timeout=60)
                        response.raise_for_status()
                        answer = response.json().get("response", "No answer found.")
                    except requests.exceptions.Timeout:
                        answer = "The query took too long to process. Could you try asking a more specific question?"
                    except Exception as e:
                        answer = f"Error connecting to backend: {str(e)}"
                
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})

# After chat state is fully updated, grab the latest response and sync the graph
last_assistant_msg = ""
if "messages" in st.session_state:
    for msg in reversed(st.session_state.messages):
        if msg["role"] == "assistant":
            last_assistant_msg = msg["content"]
            break

# Extract alphanumeric IDs to filter the PyVis graph
extracted_ids = tuple(re.findall(r'\b[A-Z0-9]{8,20}\b', last_assistant_msg)) if last_assistant_msg else tuple()

# Inject the visual back into the placeholder at the top of the column
with graph_placeholder.container():
    with st.spinner("Rendering graph topology..."):
        graph_html = generate_graph_html(extracted_ids)
        components.html(graph_html, height=820, scrolling=False)