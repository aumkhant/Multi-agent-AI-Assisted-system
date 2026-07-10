from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.tools.base import ToolMetadata, logged_tool_call


class FilmResult(BaseModel):
    title: str
    category: str
    rating: str
    rental_rate: float
    streaming_available: bool


class SearchFilmCatalogInput(BaseModel):
    query: str


class SearchFilmCatalogOutput(BaseModel):
    results: list[FilmResult]


METADATA = ToolMetadata(
    name="search_film_catalog",
    description="Search the film catalog by title and return category, rating, rental rate, "
    "and streaming availability.",
    input_schema=SearchFilmCatalogInput.model_json_schema(),
    output_schema=SearchFilmCatalogOutput.model_json_schema(),
    error_behavior="Returns an empty results list when no film matches; never raises for a "
    "missing match.",
    auth_requirement="none (public catalog data)",
    ownership_boundary="Reads only from film/category/film_category; no writes.",
    backed_by="postgres:pagila",
)

_QUERY = text(
    """
    SELECT f.title,
           c.name AS category,
           f.rating,
           f.rental_rate,
           f.streaming_available
    FROM film f
    JOIN film_category fc ON fc.film_id = f.film_id
    JOIN category c ON c.category_id = fc.category_id
    WHERE f.title ILIKE :pattern
    ORDER BY f.title
    LIMIT 10
    """
)


def search_film_catalog(
    session: Session, conversation_id: str, params: SearchFilmCatalogInput
) -> SearchFilmCatalogOutput:
    with logged_tool_call("search_film_catalog", conversation_id):
        rows = session.execute(_QUERY, {"pattern": f"%{params.query}%"}).mappings().all()
        results = [
            FilmResult(
                title=row["title"],
                category=row["category"],
                rating=row["rating"] or "NR",
                rental_rate=float(row["rental_rate"]),
                streaming_available=row["streaming_available"],
            )
            for row in rows
        ]
        return SearchFilmCatalogOutput(results=results)
