from typing import List
from pydantic import BaseModel, Field

class OrderAgainResponse(BaseModel):
    """Response schema for the Order Again endpoint.

    A simple list of product identifiers (e.g., SKUs) that the user is likely to reorder.
    """

    products: List[str] = Field(default_factory=list, description="List of product SKUs in recency order")
