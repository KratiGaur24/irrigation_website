from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.services.location_service import search_locations

router = APIRouter(tags=["locations"])


@router.get("/locations/search")
async def locations(q: str = Query(min_length=2, max_length=150), language: Literal['en', 'hi'] = 'en'):
    if len(q.strip()) < 2:
        raise HTTPException(422, "Enter at least two characters")
    return await search_locations(q.strip(), language)
