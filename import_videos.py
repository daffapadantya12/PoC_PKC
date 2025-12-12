import os
import sys
from pathlib import Path
from mcard import MCard, CardCollection
from mcard.engine.sqlite_engine import SQLiteEngine, SQLiteConnection

# Configuration
DATA_DIR = Path("data")
JSON_FILE = DATA_DIR / "videos.json"
DB_FILE = DATA_DIR / "DEFAULT_DB_FILE.db"

def main():
    print(f"--- MCard Import Script ---")
    
    # 1. Check if files exist
    if not JSON_FILE.exists():
        print(f"Error: JSON file not found at {JSON_FILE}")
        sys.exit(1)
        
    print(f"Reading {JSON_FILE}...")
    with open(JSON_FILE, "rb") as f:
        file_content = f.read()
    
    print(f"Read {len(file_content)} bytes.")

    # 2. Initialize Collection with specific DB
    # We need to manually initialize the engine to point to our specific DB file
    # Based on our inspection: CardCollection(engine=..., engine_type='sqlite', db_path=...)
    # But let's check if we can just pass db_path to CardCollection or if we need to build the engine.
    # The signature we found was: (self, engine=None, engine_type: str = 'sqlite', db_path: str = None)
    
    print(f"Connecting to database at {DB_FILE}...")
    
    # Ensure directory exists (it should)
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # According to signature, we can just pass db_path
        collection = CardCollection(db_path=str(DB_FILE))
        print("Collection initialized.")
    except Exception as e:
        print(f"Error initializing collection: {e}")
        # Fallback to explicit engine creation if needed (based on previous errors with schema)
        try:
            print("Attempting explicit engine creation...")
            conn = SQLiteConnection(str(DB_FILE))
            engine = SQLiteEngine(connection=conn)
            collection = CardCollection(engine=engine)
            print("Collection initialized with explicit engine.")
        except Exception as e2:
            print(f"Critical error: {e2}")
            sys.exit(1)

    # 3. Create MCard
    print("Creating MCard...")
    card = MCard(file_content)
    
    # 4. Save to DB
    print("Saving to database...")
    try:
        hash_value = collection.add(card)
        print(f"\n✅ Success! Saved to MCard.")
        print(f"🔑 Hash: {hash_value}")
        
        # 5. Verify
        print("\nVerifying retrieval...")
        retrieved_card = collection.get(hash_value)
        if retrieved_card:
            print("✅ Verified: Card retrieved successfully.")
            print(f"Content length: {len(retrieved_card.content)} bytes")
            if retrieved_card.content == file_content:
                 print("✅ Verified: Content matches exactly.")
            else:
                 print("❌ Error: Content mismatch!")
        else:
            print("❌ Error: Could not retrieve card!")
            
    except Exception as e:
        print(f"Error saving card: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
