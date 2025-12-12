from typing import Optional
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from mcard.config.logging import (
    SecurityAuditLogger,
    get_logger,
    setup_logging,
)
from mcard.model.card import MCard
from mcard.model.card_collection import CardCollection

# Configure logging
setup_logging()
logger = get_logger(__name__)
security_audit = SecurityAuditLogger()

# Initialize FastAPI app
app = FastAPI(
    title="MCard API (Custom)",
    description="API for managing MCard content-addressable storage (Extended).",
    version="1.0.0",
)

# Initialize CardCollection. This will use the default database path.
try:
    # Explicitly point to the data directory just in case
    card_collection = CardCollection(db_path="data/DEFAULT_DB_FILE.db")
    db_path = getattr(card_collection.engine, "db_path", "unknown")
    logger.info(f"CardCollection initialized with DB at: {db_path}")
except Exception as e:
    logger.critical(f"Failed to initialize CardCollection: {e}")
    raise RuntimeError("Could not initialize database connection.") from e


@app.post("/content/cards", status_code=201)
async def store_content_card(
    content: UploadFile = File(...),
    metadata: Optional[str] = Form(None),  # Metadata sent as a JSON string
):
    try:
        file_content = await content.read()
        if not file_content:
            raise HTTPException(status_code=400, detail="Content cannot be empty.")

        mcard = MCard(content=file_content)
        card_hash = card_collection.add(mcard)
        stored_card = card_collection.get(mcard.get_hash())
        if not stored_card:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve card after adding."
            )

        response_data = {
            "hash": stored_card.get_hash(),
            "content_type": stored_card.get_content_type(),
            "g_time": stored_card.get_g_time(),
            "message": "Content stored successfully",
        }

        if card_hash != mcard.get_hash():
            collision_msg = (
                f"Content already exists or a hash collision occurred. "
                f"Event card created with hash: {card_hash}"
            )
            response_data["message"] = collision_msg
            response_data["event_hash"] = card_hash

        return response_data

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error while creating card: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error storing content: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


class CardResponse(BaseModel):
    hash: str
    content_type: str
    g_time: str
    metadata: Optional[dict] = None


class PaginatedCardResponse(BaseModel):
    items: list[CardResponse]
    total_items: int
    page_number: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


@app.get("/content/cards", response_model=PaginatedCardResponse)
async def list_content_cards(
    query: Optional[str] = None, page: int = 1, page_size: int = 10
):
    try:
        if query:
            page_obj = card_collection.search_by_content(
                search_string=query, page_number=page, page_size=page_size
            )
        else:
            page_obj = card_collection.get_page(page_number=page, page_size=page_size)

        response_items = [
            CardResponse(
                hash=card.get_hash(),
                content_type=card.get_content_type(),
                g_time=card.get_g_time(),
            )
            for card in page_obj.items
        ]

        return PaginatedCardResponse(
            items=response_items,
            total_items=page_obj.total_items,
            page_number=page_obj.page_number,
            page_size=page_obj.page_size,
            total_pages=page_obj.total_pages,
            has_next=page_obj.has_next,
            has_previous=page_obj.has_previous,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing cards: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/content/cards/{hash}", response_model=CardResponse)
async def get_content_card(hash: str):
    try:
        card = card_collection.get(hash)
        if not card:
            raise HTTPException(status_code=404, detail="Card not found.")

        return CardResponse(
            hash=card.get_hash(),
            content_type=card.get_content_type(),
            g_time=card.get_g_time(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving card {hash}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

# --- EXTENDED ENDPOINT ---
@app.get("/content/cards/{hash}/raw")
async def get_raw_content_card(hash: str):
    """
    Retrieve the raw content of a card by its hash.
    """
    try:
        card = card_collection.get(hash)
        if not card:
            raise HTTPException(status_code=404, detail="Card not found.")
        
        # Determine media type suitable for browser/client
        media_type = "application/octet-stream"
        ct = card.get_content_type()
        if ct == "application/json":
             media_type = "application/json"
        elif ct.startswith("text/"):
             media_type = ct
        elif ct.startswith("image/"):
             media_type = ct
        
        return Response(content=card.content, media_type=media_type)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving card content {hash}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/content/cards/{hash}", status_code=204)
async def delete_content_card(hash: str):
    try:
        success = card_collection.delete(hash)
        if not success:
            raise HTTPException(
                status_code=404, detail="Card not found or could not be deleted."
            )
        return
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting card {hash}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


def start_api_server():
    """Starts the Uvicorn server."""
    logger.info("Starting Custom MCard API server...")
    uvicorn.run(app, host="0.0.0.0", port=28302, log_level="info")


if __name__ == "__main__":
    start_api_server()
