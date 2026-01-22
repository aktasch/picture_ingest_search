"""Image ingestion and vector search for MongoDB multimodal embeddings."""
import os
import sys
import base64
import io
from dotenv import load_dotenv
import voyageai.client as voyageai
from PIL import Image
from pymongo import MongoClient

# Load configuration from .env (fallback to existing values)
load_dotenv()
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY", "")
MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = os.getenv("DB_NAME", "")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "pictures")
IMAGES_DIR = os.getenv("IMAGES_DIR", "./my_pictures")

# Initialize Clients
vo = voyageai.Client(api_key=VOYAGE_API_KEY)
mongo_client = MongoClient(MONGO_URI)
collection = mongo_client[DB_NAME][COLLECTION_NAME]

def process_and_encode_image(file_path, max_pixels=15000000, max_bytes=20000000):
    """
    Resizes image to fit pixel limits and compresses to fit byte limits.
    Returns the formatted Base64 Data URL.
    """
    with Image.open(file_path) as img:
        # 1. Handle Pixel Limit (e.g., your 18MP image)
        width, height = img.size
        current_pixels = width * height

        if current_pixels > max_pixels:
            scale_factor = (max_pixels / current_pixels) ** 0.5
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            print(f"Resized {os.path.basename(file_path)} to {new_width}x{new_height}")

        # 2. Handle File Size Limit (Iterative Compression)
        # Convert to RGB if necessary (e.g., for RGBA/PNG to JPEG conversion)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        quality = 95
        output_buffer = io.BytesIO()

        while True:
            output_buffer.seek(0)
            output_buffer.truncate()
            img.save(output_buffer, format="JPEG", quality=quality)

            # Base64 encoding increases size by ~33%, so we check against raw bytes
            # with a safety margin for the base64 overhead.
            current_size = output_buffer.tell()
            if current_size <= (max_bytes * 0.7) or quality <= 20:
                break
            quality -= 10  # Reduce quality and retry

        encoded_string = base64.b64encode(output_buffer.getvalue()).decode('utf-8')
        return f"data:image/jpeg;base64,{encoded_string}"

def ingest_pictures(directory_path: str):
    """Ingest images from directory and create embeddings in MongoDB."""
    valid_extensions = ('.jpg', '.jpeg', '.png', '.webp')

    for filename in os.listdir(directory_path):
        if filename.lower().endswith(valid_extensions):
            image_path = os.path.join(directory_path, filename)

            try:
                # Optimized encoding with resizing and compression
                b64_image = process_and_encode_image(image_path)

                multimodal_input = {
                    "content": [
                        {
                            "type": "image_base64",
                            "image_base64": b64_image
                        }
                    ]
                }

                response = vo.multimodal_embed(
                    inputs=[multimodal_input],
                    model="voyage-multimodal-3.5",
                    input_type="document"
                )

                embedding = response.embeddings[0]

                collection.insert_one({
                    "file_name": filename,
                    "embedding": embedding,
                    "metadata": {"path": image_path}
                })
                print(f"Indexed: {filename}")

            except OSError as e:
                print(f"Failed {filename}: {e}")

def search_pictures(query_text: str, limit: int = 5):
    """
    Converts a text search term into an embedding and finds
    the most relevant pictures using MongoDB Vector Search.
    """
    # 1. Generate embedding for the search query
    # Use input_type="query" for better retrieval performance
    query_response = vo.multimodal_embed(
        inputs=[[query_text]],
        model="voyage-multimodal-3.5",
        input_type="query"
    )
    query_embedding = query_response.embeddings[0]

    # 2. Perform MongoDB Vector Search
    pipeline = [
        {
            "$vectorSearch": {
                "index": "default",  # Must match the index name created in Atlas
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": 100,
                "limit": limit
            }
        },
        {
            "$project": {
                "file_name": 1,
                "score": {"$meta": "vectorSearchScore"}
            }
        }
    ]

    matches = list(collection.aggregate(pipeline))

    print(f"\nResults for '{query_text}':")
    for res in matches:
        print(f" - {res['file_name']} (Score: {res['score']:.4f})")
    return matches

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python picture_ingest_search.py [ingest|search] [search_term_if_searching]")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "ingest":
        # Adjust the path to your image folder as neede
        print(f"Starting ingestion from {IMAGES_DIR}...")
        ingest_pictures(IMAGES_DIR)

    elif command == "search":
        if len(sys.argv) < 3:
            msg = "Error: Please provide a search term. "
            msg += "Example: python picture_ingest_search.py search 'red car'"
            print(msg)
            sys.exit(1)

        SEARCH_TERM = " ".join(sys.argv[2:])
        results = search_pictures(SEARCH_TERM, limit=1)
        for result in results:
            doc = collection.find_one({"file_name": result["file_name"]})
            if doc and doc.get("metadata"):
                img_path = doc["metadata"]["path"]
                Image.open(img_path).show()

    else:
        print(f"Unknown command: {command}. Use 'ingest' or 'search'.")
