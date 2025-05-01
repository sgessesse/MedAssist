import os
import sys
import chromadb
# Removed chromadb.config import as Settings might be deprecated or part of client
# from chromadb.config import Settings
# Use specific loaders/splitters as needed
# from langchain_community.document_loaders import DirectoryLoader, UnstructuredFileLoader # Example loader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document # Ensure Document is explicitly imported
from dotenv import load_dotenv
import google.generativeai as genai
import logging
import requests
from bs4 import BeautifulSoup # Keep for potential future use (Merck)
import lxml.etree as ET
import time
import zipfile
import io

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables (.env file in project root)
load_dotenv(dotenv_path=os.path.join(project_root, '.env'))

# --- Constants ---
DATA_DOWNLOAD_DIR = os.path.join(project_root, "data", "downloaded")
MEDLINE_SUBDIR = os.path.join(DATA_DOWNLOAD_DIR, "medlineplus")
CHROMA_PERSIST_DIR = os.path.join(project_root, "data", "chroma_db")
CHROMA_COLLECTION_NAME = "medical_knowledge"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150 # Increased slightly
EMBEDDING_MODEL_NAME = "models/text-embedding-004"

# --- URLs and Paths ---
# Find the *actual* link to the compressed file from the page dynamically or update manually
# Let's try to scrape the link from the xml.html page
MEDLINE_XML_INFO_URL = "https://medlineplus.gov/xml.html"
# The actual XML file extracted from the zip
MEDLINE_EXTRACTED_XML_NAME = "healthtopics.xml" # Default name, might change
MEDLINE_XML_PATH = os.path.join(MEDLINE_SUBDIR, MEDLINE_EXTRACTED_XML_NAME)

PUBMED_FTP_URL = "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/"
MERCK_MANUALS_URL = "https://www.merckmanuals.com/home"
OPENFDA_DRUG_LABEL_ENDPOINT = "https://api.fda.gov/drug/label.json"
OPENFDA_LIMIT = 100

# --- Helper Functions ---

def ensure_dir_exists(dir_path):
    """Creates a directory if it doesn't exist."""
    if not os.path.exists(dir_path):
        logging.info(f"Creating directory: {dir_path}")
        os.makedirs(dir_path)

def configure_google_api():
    """Configures the Google Generative AI SDK."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logging.error("GOOGLE_API_KEY not found in environment variables.")
        sys.exit(1)
    try:
        genai.configure(api_key=api_key)
        logging.info("Google Generative AI SDK configured.")
    except Exception as e:
        logging.error(f"Error configuring Google SDK: {e}")
        sys.exit(1)

# --- Data Loading Functions ---

def download_and_extract_medlineplus(info_url, target_dir):
    """Finds the latest compressed XML link, downloads, and extracts it."""
    ensure_dir_exists(target_dir)
    extracted_xml_path = None
    try:
        logging.info(f"Fetching MedlinePlus XML info page: {info_url}")
        response = requests.get(info_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the link to the *compressed* health topic XML
        # This relies on the webpage structure - might need adjustment if site changes
        compressed_link = soup.find('a', string=lambda t: t and "MedlinePlus Compressed Health Topic XML" in t)

        if not compressed_link or not compressed_link.has_attr('href'):
            logging.error("Could not find the compressed MedlinePlus XML download link.")
            return None

        # Construct absolute URL if relative
        download_url = compressed_link['href']
        if not download_url.startswith(('http:', 'https:')):
            from urllib.parse import urljoin
            download_url = urljoin(info_url, download_url)

        logging.info(f"Found download link: {download_url}")
        logging.info("Downloading MedlinePlus compressed XML...")
        zip_response = requests.get(download_url, stream=True, timeout=60)
        zip_response.raise_for_status()

        # Extract from memory
        with zipfile.ZipFile(io.BytesIO(zip_response.content)) as z:
            # Find the XML file within the zip (assuming one main XML)
            xml_files = [f for f in z.namelist() if f.lower().endswith('.xml')]
            if not xml_files:
                logging.error("No XML file found inside the downloaded zip.")
                return None
            # Handle case with multiple XMLs if necessary, here taking the first
            xml_filename_in_zip = xml_files[0]
            global MEDLINE_EXTRACTED_XML_NAME # Update global constant if needed
            MEDLINE_EXTRACTED_XML_NAME = os.path.basename(xml_filename_in_zip)
            extracted_xml_path = os.path.join(target_dir, MEDLINE_EXTRACTED_XML_NAME)
            logging.info(f"Extracting {xml_filename_in_zip} to {extracted_xml_path}...")
            z.extract(xml_filename_in_zip, path=target_dir)
            # Rename if the extracted file name doesn't match the target path exactly (rare)
            if os.path.basename(extracted_xml_path) != xml_filename_in_zip:
                 os.rename(os.path.join(target_dir, xml_filename_in_zip), extracted_xml_path)

        logging.info("MedlinePlus XML downloaded and extracted successfully.")
        return extracted_xml_path

    except requests.exceptions.RequestException as e:
        logging.error(f"Error downloading MedlinePlus data: {e}")
        return None
    except zipfile.BadZipFile:
        logging.error("Downloaded file is not a valid zip archive.")
        return None
    except Exception as e:
        logging.error(f"An error occurred during MedlinePlus download/extraction: {e}")
        return None

def load_medlineplus_docs(file_path):
    """Loads and parses the extracted MedlinePlus XML data."""
    logging.info(f"Loading MedlinePlus data from {file_path}...")
    docs = []
    if not file_path or not os.path.exists(file_path):
        logging.warning(f"MedlinePlus file path invalid or not found: {file_path}. Skipping.")
        return docs
    try:
        # Use iterparse for potentially large XML files
        context = ET.iterparse(file_path, events=('end',), tag='health-topic')
        count = 0
        for event, elem in context:
            title = elem.get('title') # Title is an attribute
            url = elem.get('url')
            lang = elem.get('language', 'English') # Default to English if missing
            summary_elem = elem.find('full-summary')
            # Extract text content from summary, handling potential HTML within
            summary = ''.join(summary_elem.itertext()).strip() if summary_elem is not None else None

            if title and url and summary and lang == 'English': # Process only English topics for now
                content = f"Title: {title}\nSummary: {summary}"
                metadata = {
                    "source": "MedlinePlus",
                    "title": title,
                    "url": url,
                    "language": lang
                }
                docs.append(Document(page_content=content, metadata=metadata))
                count += 1

            # It's important to clear the element from memory after processing
            elem.clear()
            # Also eliminate now-empty references from the root node to it
            while elem.getprevious() is not None:
                del elem.getparent()[0]

        del context # Free up parser memory
        logging.info(f"Loaded {count} English documents from MedlinePlus.")
    except ET.XMLSyntaxError as e:
        logging.error(f"Error parsing MedlinePlus XML (invalid XML): {e}")
    except Exception as e:
        logging.error(f"Error processing MedlinePlus XML: {e}")
    return docs

def load_pubmed_docs():
    """Downloads (if necessary) and loads PubMed Central OA abstracts."""
    logging.warning("PubMed loading via FTP is not implemented. Requires manual download or alternative access method. Skipping.")
    return []

def load_merck_manuals_docs():
    """Scrapes or loads Merck Manuals Consumer Version content."""
    logging.warning("Merck Manuals loading via scraping is not implemented due to complexity and potential site changes. Skipping.")
    return []

def load_openfda_docs(limit_per_run=500):
    """Fetches drug label data from openFDA API."""
    logging.info("Loading openFDA drug label data...")
    docs = []
    try:
        skip = 0
        total_fetched = 0
        processed_ids = set() # Avoid duplicates if API returns overlapping results

        while total_fetched < limit_per_run:
            batch_limit = min(OPENFDA_LIMIT, limit_per_run - total_fetched)
            if batch_limit <= 0: break
            # Adding a search filter for potentially useful fields (e.g., indications_and_usage exists)
            url = f"{OPENFDA_DRUG_LABEL_ENDPOINT}?search=_exists_:indications_and_usage&limit={batch_limit}&skip={skip}"
            logging.info(f"Fetching openFDA batch: skip={skip}, limit={batch_limit}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            if 'results' not in data or not data['results']:
                logging.info("No more results from openFDA for this query.")
                break

            batch_docs = []
            for result in data['results']:
                # Use 'id' or 'spl_id' as a unique identifier
                result_id = result.get('id') or (result.get('spl_id') and result['spl_id'][0])
                if not result_id or result_id in processed_ids:
                    continue # Skip if no ID or already processed
                processed_ids.add(result_id)

                content_parts = []
                metadata = {"source": "openFDA", "id": result_id}

                brand_name = result.get('brand_name', [None])[0]
                generic_name = result.get('generic_name', [None])[0]
                if brand_name: metadata['brand_name'] = brand_name
                if generic_name: metadata['generic_name'] = generic_name
                title = f"{brand_name or generic_name or 'Drug Label'}"
                content_parts.append(f"Title: {title}")

                # Extract key sections if they exist (handle potential list/string issues)
                def get_first_string(data_list):
                    return data_list[0] if isinstance(data_list, list) and data_list else str(data_list)

                if 'description' in result: content_parts.append(f"Description: {get_first_string(result['description'])}")
                if 'indications_and_usage' in result: content_parts.append(f"Indications: {get_first_string(result['indications_and_usage'])}")
                if 'dosage_and_administration' in result: content_parts.append(f"Dosage: {get_first_string(result['dosage_and_administration'])}")
                if 'warnings' in result: content_parts.append(f"Warnings: {get_first_string(result['warnings'])}")
                if 'contraindications' in result: content_parts.append(f"Contraindications: {get_first_string(result['contraindications'])}")
                if 'adverse_reactions' in result: content_parts.append(f"Adverse Reactions: {get_first_string(result['adverse_reactions'])}")

                content = "\n\n".join(content_parts)
                if content:
                    batch_docs.append(Document(page_content=content.strip(), metadata=metadata))

            docs.extend(batch_docs)
            total_fetched += len(data['results'])
            # Crude check if we might be at the end
            api_total = data.get('meta', {}).get('results', {}).get('total', float('inf'))
            if skip + len(data['results']) >= api_total:
                logging.info("Reached reported total results from openFDA.")
                break
            skip += batch_limit
            time.sleep(1) # Be polite to the API

        logging.info(f"Loaded {len(docs)} documents from openFDA (processed {len(processed_ids)} unique IDs, limited to {limit_per_run}).")

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching openFDA data: {e}")
    except Exception as e:
        logging.error(f"Error processing openFDA data: {e}")
    return docs

# --- Main Ingestion Logic ---

def main():
    configure_google_api()
    ensure_dir_exists(DATA_DOWNLOAD_DIR)
    ensure_dir_exists(MEDLINE_SUBDIR)
    ensure_dir_exists(CHROMA_PERSIST_DIR)

    # --- 1. Load Data ---
    logging.info("--- Starting Data Loading Phase ---")
    all_docs = [] # Initialize list for LangChain documents

    # Download and load MedlinePlus
    medline_xml_file = download_and_extract_medlineplus(MEDLINE_XML_INFO_URL, MEDLINE_SUBDIR)
    if medline_xml_file:
        all_docs.extend(load_medlineplus_docs(medline_xml_file))
    else:
        logging.warning("Failed to download or process MedlinePlus data.")

    # Load openFDA
    all_docs.extend(load_openfda_docs(limit_per_run=1000)) # Increased limit slightly

    # Placeholders for other sources
    all_docs.extend(load_pubmed_docs())
    all_docs.extend(load_merck_manuals_docs())

    if not all_docs:
        logging.error("No documents were loaded successfully. Exiting.")
        sys.exit(1)

    logging.info(f"--- Total documents loaded: {len(all_docs)} ---")

    # --- 2. Split Documents ---
    logging.info("--- Starting Document Splitting Phase ---")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        add_start_index=True, # Add start index to metadata for potential reference
    )
    splits = text_splitter.split_documents(all_docs)
    logging.info(f"--- Total documents split into {len(splits)} chunks ---")

    if not splits:
        logging.error("No document chunks were generated after splitting. Exiting.")
        sys.exit(1)

    # --- 3. Initialize Embeddings ---
    logging.info(f"--- Initializing Embeddings Model: {EMBEDDING_MODEL_NAME} ---")
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL_NAME)
        # Simple test call
        # test_emb = embeddings.embed_query("Test embedding")
        # logging.info(f"Embedding test successful (vector dim: {len(test_emb)})")
    except Exception as e:
        logging.error(f"Failed to initialize or use Google Embeddings: {e}")
        logging.error("Ensure GOOGLE_API_KEY is valid, model name is correct, and network access is available.")
        sys.exit(1)

    # --- 4. Initialize ChromaDB and Ingest ---
    logging.info(f"--- Initializing ChromaDB (persist path: {CHROMA_PERSIST_DIR}) ---")
    try:
        vectorstore = Chroma(
            collection_name=CHROMA_COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=CHROMA_PERSIST_DIR,
        )

        # More robust check for existing data (optional, simple check here)
        # existing_count = vectorstore._collection.count()
        # if existing_count > 0:
        #     logging.warning(f"Collection '{CHROMA_COLLECTION_NAME}' already contains {existing_count} documents. Re-ingesting might duplicate data or is unnecessary.")
            # Add logic to skip if needed: sys.exit(0)

        logging.info(f"--- Starting Ingestion into ChromaDB ({len(splits)} chunks) ---")
        # Ingest in batches for large datasets
        batch_size = 100
        for i in range(0, len(splits), batch_size):
            batch = splits[i:i + batch_size]
            batch_ids = [f"{doc.metadata.get('source', 'unknown')}_{doc.metadata.get('id', i+j)}_{doc.metadata.get('start_index', j)}" for j, doc in enumerate(batch)]
            vectorstore.add_documents(documents=batch, ids=batch_ids)
            logging.info(f"Ingested batch {i // batch_size + 1} / {len(splits) // batch_size + 1}")
            time.sleep(0.5) # Small delay between batches

        # Chroma automatically persists with the client now, explicit persist might not be needed
        # vectorstore.persist()
        logging.info("--- Ingestion Complete --- ")

    except Exception as e:
        logging.error(f"Error during ChromaDB initialization or ingestion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    logging.info(f"Vector store population complete. DB located at: {CHROMA_PERSIST_DIR}")

if __name__ == "__main__":
    main() 