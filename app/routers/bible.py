"""API routes for Bible verse retrieval."""
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.schemas import BibleVerseResponse, BiblePassageResponse
from app.services.bible_service import BibleService, get_bible_service
from app.utils.exceptions import ValidationError

router = APIRouter(prefix="/api", tags=["bible"])


async def _fetch_bible_verse(
    ref: str,
    service: BibleService,
) -> BibleVerseResponse:
    try:
        verse = service.get_verse(ref)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail) from exc

    if verse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verse not found")

    return verse


@router.get("/bible/verse", response_model=BibleVerseResponse)
async def fetch_bible_verse(
    ref: str = Query(..., description="Scripture reference, e.g. 'John 3:16'"),
    service: BibleService = Depends(get_bible_service),
):
    """Fetch a Bible verse by scripture reference."""
    return await _fetch_bible_verse(ref, service)


@router.get("/verse", response_model=BibleVerseResponse, include_in_schema=False)
async def fetch_bible_verse_legacy(
    ref: str = Query(..., description="Scripture reference, e.g. 'John 3:16'"),
    service: BibleService = Depends(get_bible_service),
):
    """Legacy route alias for backward compatibility."""
    return await _fetch_bible_verse(ref, service)


@router.get("/bible/passage", response_model=BiblePassageResponse)
async def fetch_bible_passage(
    reference: str = Query(..., min_length=3, description="Reference like 'John 3:16-18' or 'Psalm 23'"),
    service: BibleService = Depends(get_bible_service),
):
    try:
        passage = service.get_passage_by_reference(reference)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail) from exc

    if passage is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passage not found")

    return passage
