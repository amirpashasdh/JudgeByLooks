from pydantic import BaseModel


class UploadResponse(BaseModel):
    session_id: str
    person_id: int
    run_folder: str
    keywords: dict[str, float]


class Product(BaseModel):
    product_id: str
    brand: str
    name: str
    category: str
    price: float
    currency: str
    price_tier: str
    similarity_score: float
    product_url: str
    image_url: str
    matched_keywords: dict[str, float]
    rank: int


class RecommendationsResponse(BaseModel):
    session_id: str
    person_id: int
    products: list[Product]
    ranking_mode: str


class RatingRequest(BaseModel):
    session_id: str
    person_id: int
    product_id: str
    contextual_fit: int
    general_taste: int


class RatingResponse(BaseModel):
    success: bool
    message: str


class FavoritesRequest(BaseModel):
    session_id: str
    person_id: int
    product_ids: list[str]


class FavoritesResponse(BaseModel):
    success: bool
    saved: int
    message: str


class BrowseResponse(BaseModel):
    session_id: str
    person_id: int
    products: list[Product]
