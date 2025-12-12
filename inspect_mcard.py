import mcard
from mcard import default_collection, MCard
import inspect

print("--- Default Collection ---")
print(f"Type: {type(default_collection)}")
print(f"Dir: {dir(default_collection)}")

# Check if we can find the db path
possible_attrs = ['storage', 'db_path', 'connection', 'engine']
for attr in possible_attrs:
    if hasattr(default_collection, attr):
        val = getattr(default_collection, attr)
        print(f"{attr}: {val} (type: {type(val)})")
        # Go deeper if it's an engine/storage
        if hasattr(val, 'db_path'):
             print(f"  -> db_path: {val.db_path}")

print("\n--- MCard Class ---")
print(f"Signature: {inspect.signature(MCard.__init__)}")
