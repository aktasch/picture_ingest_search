# picture_ingest_search
Sample implementation to ingest pictures using voyage.ai multimodal embeddings and store them in a MongoDB vector collection.

## Quick setup

1. Create a project virtual environment and activate it:

   macOS / Linux:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   Windows (PowerShell):

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Upgrade pip and install dependencies:

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. (Optional) Save exact pinned dependencies:

   ```bash
   pip freeze > requirements.txt
   ```

## Configuration (.env)

Create a `.env` file at the project root with the following variables (an example is already included in the repo):

```
VOYAGE_API_KEY=your_voyage_api_key_here
MONGO_URI=mongodb+srv://<user>:<pass>@cluster.example.net/
DB_NAME=voyageMultimodal
COLLECTION_NAME=pictures
IMAGES_DIR=./my_pictures
```

The script will load these values via `python-dotenv` and fall back to sensible defaults if a variable is missing.

Note:
- By default the project includes an empty `my_pictures/` folder tracked via `my_pictures/.gitkeep` so you have a place to drop images.
- The repository `.gitignore` already excludes `.env` so your secrets won't be committed.

You can change the images directory either by editing the `IMAGES_DIR` value in your `.env` file or by setting it inline when running the command, for example:

```bash
IMAGES_DIR=./other_folder python picture_ingest_search.py ingest
```

## MongoDB Vector Index (Atlas Search)

Your vector field (`embedding`) must be indexed for fast vector retrieval. In MongoDB Atlas you can create a custom Search index and paste the following JSON as the index definition. Make sure `numDimensions` matches the embedding dimensionality used by your model (1024 below):

```json
{
   "fields": [
      {
         "numDimensions": 1024,
         "path": "embedding",
         "similarity": "cosine",
         "type": "vector"
      }
   ]
}
```

Steps (Atlas UI):

1. Open your Atlas cluster and navigate to the **Search** tab.
2. Click **Create Search Index** and choose **Custom**.
3. Paste the JSON above and create the index for the target database/collection.

Alternative (API / Terraform):
- Use Atlas search index API or the Terraform provider to apply equivalent JSON to create the index programmatically.

After the index is created the script's `$vectorSearch` pipeline will be able to use the `embedding` field for similarity search.

## Usage

There is a CLI script `picture_ingest_search.py` with two commands:

- Ingest images from a directory and index them in MongoDB:

```bash
python picture_ingest_search.py ingest
```

- Search images by text (generates an embedding for the query and performs vector search):

```bash
python picture_ingest_search.py search "red car"
```

The search command displays results and will open matched images using the system image viewer.

## Notes and troubleshooting

- Ensure MongoDB has the appropriate vector index (the script uses the `embedding` field and index name `default` in its pipeline). Configure Atlas or your MongoDB deployment accordingly.
- If `from dotenv import load_dotenv` fails, ensure you installed dependencies into the active venv: `pip install python-dotenv`.
- To run linting locally:

```bash
pylint picture_ingest_search.py
```
