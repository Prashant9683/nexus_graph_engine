import os
import json
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

def read_jsonl(directory):
    records = []
    if not os.path.exists(directory):
        print(f"Skipping {directory}: not found.")
        return records
    for filename in os.listdir(directory):
        if filename.endswith(".jsonl"):
            filepath = os.path.join(directory, filename)
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
    return records

def ingest_customers(tx, data):
    query = """
    UNWIND $data AS row
    MERGE (c:Customer {customer_id: row.businessPartner})
    SET c.name = row.businessPartnerFullName,
        c.category = row.businessPartnerCategory,
        c.grouping = row.businessPartnerGrouping
    """
    tx.run(query, data=data)

def ingest_products(tx, data):
    query = """
    UNWIND $data AS row
    MERGE (p:Product {product_id: row.product})
    SET p.product_type = row.productType,
        p.gross_weight = toFloat(row.grossWeight),
        p.net_weight = toFloat(row.netWeight),
        p.weight_unit = row.weightUnit,
        p.product_group = row.productGroup
    """
    tx.run(query, data=data)

def ingest_orders(tx, data):
    query = """
    UNWIND $data AS row
    MERGE (o:SalesOrder {order_id: row.salesOrder})
    SET o.type = row.salesOrderType,
        o.date = row.creationDate,
        o.amount = toFloat(row.totalNetAmount),
        o.currency = row.transactionCurrency,
        o.status = row.overallDeliveryStatus
    WITH o, row
    MATCH (c:Customer {customer_id: row.soldToParty})
    MERGE (c)-[:PLACED]->(o)
    """
    tx.run(query, data=data)

def ingest_order_items(tx, data):
    query = """
    UNWIND $data AS row
    MATCH (o:SalesOrder {order_id: row.salesOrder})
    MATCH (p:Product {product_id: row.material})
    MERGE (o)-[rel:CONTAINS]->(p)
    SET rel.quantity = toFloat(row.requestedQuantity),
        rel.amount = toFloat(row.netAmount)
    """
    tx.run(query, data=data)

def ingest_deliveries(tx, data):
    query = """
    UNWIND $data AS row
    MERGE (d:OutboundDelivery {delivery_id: row.deliveryDocument})
    SET d.date = row.creationDate,
        d.status = row.overallGoodsMovementStatus,
        d.shipping_point = row.shippingPoint
    """
    tx.run(query, data=data)

def ingest_delivery_items(tx, data):
    query = """
    UNWIND $data AS row
    MATCH (d:OutboundDelivery {delivery_id: row.deliveryDocument})
    MATCH (o:SalesOrder {order_id: row.referenceSdDocument})
    MERGE (d)-[rel:DELIVERS]->(o)
    SET rel.quantity = toFloat(row.actualDeliveryQuantity)
    """
    tx.run(query, data=data)

def ingest_invoices(tx, data):
    query = """
    UNWIND $data AS row
    MERGE (i:BillingDocument {billing_document: row.billingDocument})
    SET i.type = row.billingDocumentType,
        i.date = row.billingDocumentDate,
        i.amount = toFloat(row.totalNetAmount),
        i.currency = row.transactionCurrency,
        i.is_cancelled = row.billingDocumentIsCancelled
    WITH i, row
    MATCH (c:Customer {customer_id: row.soldToParty})
    MERGE (i)-[:BILLED_TO]->(c)
    """
    tx.run(query, data=data)

def ingest_invoice_items(tx, data):
    query1 = """
    UNWIND $data AS row
    MATCH (i:BillingDocument {billing_document: row.billingDocument})
    MATCH (o:SalesOrder {order_id: row.referenceSdDocument})
    MERGE (i)-[:BILLS]->(o)
    """
    tx.run(query1, data=data)
    
    query2 = """
    UNWIND $data AS row
    MATCH (i:BillingDocument {billing_document: row.billingDocument})
    MATCH (d:OutboundDelivery {delivery_id: row.referenceSdDocument})
    MERGE (i)-[:BILLS]->(d)
    """
    tx.run(query2, data=data)

def ingest_journal_entries(tx, data):
    query = """
    UNWIND $data AS row
    MERGE (j:JournalEntry {journal_entry: row.accountingDocument})
    SET j.date = row.postingDate,
        j.amount = toFloat(row.amountInTransactionCurrency),
        j.currency = row.transactionCurrency,
        j.account = row.glAccount
    WITH j, row
    MATCH (i:BillingDocument {billing_document: row.referenceDocument})
    MERGE (j)-[:CLEARS]->(i)
    """
    tx.run(query, data=data)

def chunker(seq, size):
    return (seq[pos:pos+size] for pos in range(0, len(seq), size))

def process_directory(directory, session, ingest_func, batch_size=2000):
    records = read_jsonl(directory)
    if not records:
        return
    for chunk in chunker(records, batch_size):
        session.execute_write(ingest_func, chunk)
    print(f"Successfully ingested {len(records)} records from {os.path.basename(directory)}")

def main():
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sap_dataset", "sap-o2c-data")
    
    with driver.session() as session:
        print("Erasing previous graph...")
        session.run("MATCH (n) DETACH DELETE n;")
        
        process_directory(os.path.join(data_dir, "business_partners"), session, ingest_customers)
        process_directory(os.path.join(data_dir, "products"), session, ingest_products)
        process_directory(os.path.join(data_dir, "sales_order_headers"), session, ingest_orders)
        process_directory(os.path.join(data_dir, "sales_order_items"), session, ingest_order_items)
        process_directory(os.path.join(data_dir, "outbound_delivery_headers"), session, ingest_deliveries)
        process_directory(os.path.join(data_dir, "outbound_delivery_items"), session, ingest_delivery_items)
        process_directory(os.path.join(data_dir, "billing_document_headers"), session, ingest_invoices)
        process_directory(os.path.join(data_dir, "billing_document_items"), session, ingest_invoice_items)
        process_directory(os.path.join(data_dir, "journal_entry_items_accounts_receivable"), session, ingest_journal_entries)

    driver.close()
    print("Ingestion complete.")

if __name__ == "__main__":
    main()
