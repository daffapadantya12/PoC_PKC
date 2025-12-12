from mcard.model.card_collection import CardCollection
from mcard.engine.sqlite_engine import SQLiteEngine
import inspect

print(f"CardCollection init: {inspect.signature(CardCollection.__init__)}")
print(f"SQLiteEngine init: {inspect.signature(SQLiteEngine.__init__)}")
