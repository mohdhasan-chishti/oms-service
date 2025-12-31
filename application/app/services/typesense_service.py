from typing import Dict, Optional
import httpx
from httpx_retry import AsyncRetryTransport, RetryPolicy
import json
from fastapi import HTTPException

# Request context
from app.middlewares.request_context import request_context

# Logger
from app.logging.utils import get_app_logger
logger = get_app_logger('typesense_service')

# Settings
from app.config.settings import OMSConfigs
configs = OMSConfigs()

TYPESENSE_API_KEY = configs.TYPESENSE_API_KEY
TYPESENSE_HOST = configs.TYPESENSE_HOST
TYPESENSE_PORT = configs.TYPESENSE_PORT
TYPESENSE_PROTOCOL = configs.TYPESENSE_PROTOCOL
TYPESENSE_COLLECTION_NAME = configs.TYPESENSE_COLLECTION_NAME
TYPESENSE_FREEBIES_COLLECTION_NAME = configs.TYPESENSE_FREEBIES_COLLECTION_NAME
TYPESENSE_INDEX_SIZE = configs.TYPESENSE_INDEX_SIZE

class TypesenseService:

    def __init__(self):
        # Set module for contextual logging
        request_context.module_name = 'typesense_service'
        self.host = TYPESENSE_HOST
        self.port = TYPESENSE_PORT
        self.protocol = TYPESENSE_PROTOCOL
        self.api_key = TYPESENSE_API_KEY
        self.collection_name = TYPESENSE_COLLECTION_NAME
        self.freebies_collection_name = TYPESENSE_FREEBIES_COLLECTION_NAME

        if not self.api_key:
            logger.error("typesense_api_key_missing")
            raise ValueError("TYPESENSE_API_KEY environment variable is required")

        self.base_url = f"{self.protocol}://{self.host}:{self.port}"
        self.headers = {
            "X-TYPESENSE-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        # Configure retry policy
        retry_policy = RetryPolicy(
            max_retries=5,
            initial_delay=0.5,
            multiplier=2.0,
            retry_on=[429, 500, 502, 503, 504]
        )
        # Create retry transport
        retry_transport = AsyncRetryTransport(policy=retry_policy)

        # Persistent async client with retry support
        self.client = httpx.AsyncClient(transport=retry_transport, timeout=60.0)

    async def close(self):
        """Explicitly close the HTTP client to free resources."""
        await self.client.aclose()

    def _get_bulk_headers(self) -> Dict[str, str]:
        """Return headers for bulk operations (JSONL format)."""
        return {
            'X-TYPESENSE-API-KEY': self.api_key,
            'Content-Type': 'text/plain'
        }

    async def make_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        content: Optional[str] = None,
        json_data: Optional[Dict] = None,
        timeout: Optional[float] = None,
        raise_for_status: bool = True
    ) -> httpx.Response:
        """Send HTTP request with automatic retry support."""
        try:
            response = await self.client.request(method=method, url=url, headers=headers, params=params, content=content, json=json_data, timeout=timeout)
            if raise_for_status:
                response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            # Log error after all retries exhausted
            if e.response.status_code in [429, 500, 502, 503, 504]:
                logger.error(f"Typesense API: All retries exhausted - HTTP {e.response.status_code} for {method} {url}")
            else:
                logger.error(f"Typesense API: HTTP {e.response.status_code} error for {method} {url}")
            raise
        except Exception as e:
            logger.error(f"Typesense API: Unexpected error for {method} {url}: {str(e)}")
            raise

    def _build_filter_query(self, base_conditions: list, product_filter_conditions: list) -> str:
        """
        Build a professional Typesense filter query from conditions.
        Args:
            base_conditions: List of base filter conditions
            product_conditions: List of product_filter_conditions to be OR'd together
        Returns:
            Complete filter query string
        """
        if not product_filter_conditions:
            return " && ".join(base_conditions)

        base_filter = " && ".join(base_conditions)
        product_filter = " || ".join(product_filter_conditions)
        return f"{base_filter} && ({product_filter})"

    async def search_documents(self, query_params: Dict[str, str], collection: str = None) -> Dict:
        """Search documents in Typesense collection.
        Args:
            query_params: Parameters for the search query
            collection: Optional collection name, defaults to self.collection_name
        Returns:
            The search response as a dictionary
        """
        target_collection = collection or self.collection_name
        url = f"{self.base_url}/collections/{target_collection}/documents/search"

        # Let make_request handle all error logging
        try:
            response = await self.make_request(method="GET", url=url, headers=self.headers, params=query_params, timeout=60.0)
            return response.json()
        except Exception as e:
            logger.error(f"TYPESENSE_API_ERROR: Error searching documents: {e}")
            raise ValueError(f"Failed to search documents in Typesense: {e}")

    async def get_all_documents(self, query_params: Dict[str, str], collection: str = None) -> Dict:
        """Fetch all documents from Typesense by paginating through all results.
        Args:
            query_params: Parameters for the search query (without page/per_page)
            collection: Optional collection name, defaults to self.collection_name

        Returns:
            Dict containing all hits and metadata with complete result set
        """
        all_hits = []
        page = 1
        per_page = query_params.get('per_page', 250)  # Default to 250 per page

        # Ensure per_page is in query params
        query_params['per_page'] = per_page
        logger.info(f"typesense_get_all_documents_started | collection={collection or self.collection_name}")

        while True:
            # Set current page
            query_params['page'] = page
            search_result = await self.search_documents(query_params, collection=collection)
            found = search_result.get('found', 0)
            hits = search_result.get('hits', [])
            logger.info(f"typesense_page_fetched | page={page} hits_count={len(hits)} total_found={found}")

            # Append hits from current page
            all_hits.extend(hits)

            # Check if we've retrieved all documents
            if len(all_hits) >= found or len(hits) == 0:
                break

            page += 1

        logger.info(f"typesense_get_all_documents_completed | total_hits={len(all_hits)} total_found={found}")

        # Return result in same format as search_documents but with all hits
        return {
            'facet_counts': search_result.get('facet_counts', []),
            'found': found,
            'hits': all_hits,
            'out_of': search_result.get('out_of', 0),
            'page': 1,  # Reset to page 1 since we're returning all results
            'request_params': search_result.get('request_params', {}),
            'search_cutoff': search_result.get('search_cutoff', False),
            'search_time_ms': search_result.get('search_time_ms', 0)
        }

    async def get_products_by_skus(self, sku_data_pairs: list, facility_name: str, origin: str = "app", price_field: str = "selling_price") -> Dict[str, Dict]:
        """
        fetch products by SKUs to avoid N+1 query problem.
        Args:
            sku_data_pairs: List of tuples [(sku, mrp), ...] 
            facility_name: Facility name to filter by
            origin: "app" or "pos"
        Returns:
            Dict mapping SKU to product data: {sku: product_dict, ...}
        """
        # size to avoid 400 Bad Request due to long filter queries
        all_products = {}

        for index in range(0, len(sku_data_pairs), TYPESENSE_INDEX_SIZE):
            index_pairs = sku_data_pairs[index:index + TYPESENSE_INDEX_SIZE]

            # Build base filter conditions
            base_conditions = [f"facility_code:={facility_name}", "is_active:=true"]

            if origin == "app":
                base_conditions.append("is_app:=true")
            elif origin == "pos":
                base_conditions.append("is_pos:=true")

            product_filter_conditions = []
            for sku, mrp, typesense_id, original_sale_price in index_pairs:
                if price_field == 'selling_price':
                    product_filter_conditions.append(f"(child_sku:=`{sku}` && mrp:={mrp} && selling_price:={original_sale_price})")
                else:
                    product_filter_conditions.append(f"(id:={typesense_id})")

            # Build complete filter using helper method
            complete_filter = self._build_filter_query(base_conditions, product_filter_conditions)

            # Log the complete filter query for debugging
            logger.info(f"typesense_query_filter | facility={facility_name} filter={complete_filter}")

            query_params = {
                "q": "*",
                "filter_by": complete_filter
            }

            logger.info(f"typesense_search_started | typesense_index_size={len(index_pairs)} facility={facility_name}")
            search_result = await self.get_all_documents(query_params, collection=self.collection_name)

            if search_result.get("hits"):
                documents = search_result.get("hits", [])
                for doc in documents:
                    product = doc["document"]
                    sku = product.get("child_sku")
                    if sku:
                        all_products[sku] = product
                        logger.info(f"typesense_product_found | sku={sku} facility={facility_name}")
            else:
                # Log detailed info about missing products
                missing_details = []
                for sku, mrp, typesense_id, original_sale_price in index_pairs:
                    missing_details.append(f"{sku}(mrp={mrp},price={original_sale_price})")
                logger.error(f"typesense_not_found | facility={facility_name} missing_products={missing_details}")

        logger.info(f"typesense_search_completed | total_skus={len(sku_data_pairs)} facility={facility_name} found_count={len(all_products)}")
        return all_products


    async def get_freebie_by_sku(self, sku: str, facility_name: str) -> Optional[Dict]:
        """Get freebie product details by SKU from freebies_products collection"""
        try:
            search_params = {
                "q": sku,
                "query_by": "sku",
                "filter_by": f"sku:={sku} && facility_code:={facility_name}",
                "per_page": 1
            }

            url = f"{self.base_url}/collections/{self.freebies_collection_name}/documents/search"
            response = await self.make_request(method="GET", url=url, headers=self.headers, params=search_params, timeout=60.0, raise_for_status=False)

            if response.status_code == 200:
                data = response.json()
                hits = data.get("hits", [])

                if hits:
                    freebie = hits[0]["document"]
                    logger.info(f"typesense_freebie_found | sku={sku} facility={facility_name}")
                    return freebie
                else:
                    logger.warning(f"typesense_freebie_not_found | sku={sku} facility={facility_name}")
                    return None

            elif response.status_code == 404:
                logger.warning(f"typesense_freebie_not_found_404 | sku={sku} facility={facility_name}")
                return None
            else:
                logger.error(f"typesense_freebie_api_error | sku={sku} facility={facility_name} status_code={response.status_code}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to fetch freebie data for SKU {sku}"
                )
        except httpx.TimeoutException:
            logger.error(f"typesense_freebie_timeout | sku={sku} facility={facility_name}", exc_info=True)
            raise HTTPException(
                status_code=500, 
                detail=f"Timeout while fetching freebie data for SKU {sku}"
            )
        except Exception as e:
            logger.error(f"typesense_freebie_error | sku={sku} facility={facility_name} error={e}", exc_info=True)
            raise HTTPException(
                status_code=500, 
                detail=f"Error fetching freebie data for SKU {sku}"
            )

    def extract_item_fields(self, product: Dict) -> Dict:
        # Extract only required fields from product
        product_data = {
            "cgst": float(product.get("cgst", 0.0)),  # tax maps to cgst
            "sgst": float(product.get("sgst", 0.0)),
            "igst": float(product.get("igst", 0.0)),
            "cess": float(product.get("cess", 0.0)),
            "selling_price_net": float(product.get("selling_price_net", 0.0)), # Price fields
            "distributor_selling_price": float(product.get("distributor_selling_price", 0.0)),
            "peer_selling_price": float(product.get("peer_selling_price", 0.0)),
            "employee_selling_price": float(product.get("employee_selling_price", 0.0)),
            "is_returnable": bool(product.get("is_returnable", False)), # Return policy fields
            "return_type": str(product.get("return_type", "00")),
            "return_window": int(product.get("return_window", 0)),
            "wh_sku": str(product.get("wh_sku", "")),  # Stock fields
            "pack_uom_quantity": int(product.get("pack_uom_qty", 1)),
            "thumbnail_url": str(product.get("thumbnail_image", "")),
            "name": str(product.get("name", "")),
            "hsn_code": str(product.get("hsn_code", "")),  # HSN code for tax purposes
            "category": str(product.get("collection_name", "")),
            "sub_category": str(product.get("parent_name", "")),
            "sub_sub_category": str(product.get("category_name", "")),
            "brand_name": str(product.get("brand_name", "")),
            "document_id": str(product.get("id", "")),
            "available_qty": int(product.get("available_qty", 0)),
            "domain_name": str(product.get("domain_name", "")),
            "provider_id": str(product.get("provider_id", "")),
            "location_id": str(product.get("location_id", ""))
        }

        return product_data

    async def get_document_by_wh_skus(self, wh_skus: list, collection: str, facility_name: str) -> Dict:
        all_documents = []

        for index in range(0, len(wh_skus), TYPESENSE_INDEX_SIZE):
            index_wh_skus = wh_skus[index:index + TYPESENSE_INDEX_SIZE]

            # Build base filter conditions
            base_conditions = [f"facility_code:={facility_name}", "is_active:=true"]
            product_filter_conditions = []
            # Build filter conditions - always build for matching pairs
            for wh_sku in index_wh_skus:
                product_filter_conditions.append(f"wh_sku:=`{wh_sku}`")

            # Build complete filter using helper method
            complete_filter = self._build_filter_query(base_conditions, product_filter_conditions)

            query_params = {
                "q": "*",
                "filter_by": complete_filter
            }

            logger.info(f"typesense_search_started | typesense_index_size={len(index_wh_skus)} facility={facility_name}")
            search_result = await self.get_all_documents(query_params, collection=collection)

            if search_result.get("hits"):
                documents = search_result.get("hits", [])
                for doc in documents:
                    doc_data = {
                        "id": doc["document"]["id"],
                        "wh_sku": doc["document"]["wh_sku"],
                        "pack_uom_qty": doc["document"].get("pack_uom_qty", 1)
                    }
                    all_documents.append(doc_data)
            else:
                logger.error(f"typesense_documents_not_found | wh_skus={index_wh_skus} facility={facility_name}")

        logger.info(f"typesense_search_completed | total_wh_skus={len(wh_skus)} facility={facility_name} documents_count={len(all_documents)}")
        return all_documents

    async def bulk_update_documents(self, documents_data: list, collection: str = None) -> Dict:
        """Bulk update multiple documents in Typesense collection.

        Performs PARTIAL UPDATE - only updates the specified fields, preserves all other fields.
        Same behavior as individual PATCH operations.
        Args:
            documents_data: List of documents with id and fields to update
                          Format: [{'id': 'doc1', 'is_available': True, 'available_qty': 10}, ...]
            collection: Optional collection name, defaults to self.collection

        Returns:
            The bulk update response as a dictionary
        """
        target_collection = collection or self.collection_name
        url = f"{self.base_url}/collections/{target_collection}/documents/import"

        all_results = []
        total_success = 0
        total_errors = 0
        
        for index in range(0, len(documents_data), TYPESENSE_INDEX_SIZE):
            docs = documents_data[index:index + TYPESENSE_INDEX_SIZE]
            
            # Convert to JSONL format (one JSON object per line)
            jsonl_data = '\n'.join(json.dumps(doc) for doc in docs)
            logger.info(f"TYPESENSE_API: Bulk updating {index//TYPESENSE_INDEX_SIZE + 1}, size={len(docs)} in collection '{target_collection}'")

            try:
                response = await self.make_request(method="POST", url=url, headers=self._get_bulk_headers(), content=jsonl_data, params={'action': 'update'}, timeout=60.0)
                logger.info(f"TYPESENSE_API: {index//TYPESENSE_INDEX_SIZE + 1} update response received")

                # Parse response - Typesense returns JSONL for bulk operations
                results = []
                for line in response.text.strip().split('\n'):
                    if line.strip():
                        result = json.loads(line)
                        results.append(result)
                        if result.get('success'):
                            total_success += 1
                        else:
                            total_errors += 1
                            logger.error(f"TYPESENSE_API: Update failed for document: {result}")

                all_results.extend(results)
                logger.info(f"TYPESENSE_API: {index//TYPESENSE_INDEX_SIZE + 1} completed - success: {len([r for r in results if r.get('success')])}, errors: {len([r for r in results if not r.get('success')])}")

            except httpx.RequestError as e:
                logger.error(f"TYPESENSE_API_ERROR: Error bulk updating {index//TYPESENSE_INDEX_SIZE + 1}: {e}")
                for doc in docs:
                    all_results.append({"success": False, "error": str(e), "document_id": doc.get('id')})
                    total_errors += 1
            except Exception as e:
                logger.error(f"TYPESENSE_API_ERROR: Unexpected error bulk updating {index//TYPESENSE_INDEX_SIZE + 1}: {e}")
                # Add error results for this
                for doc in docs:
                    all_results.append({"success": False, "error": str(e), "document_id": doc.get('id')})
                    total_errors += 1
        
        logger.info(f"TYPESENSE_API: Bulk update completed - total_documents={len(documents_data)}, success={total_success}, errors={total_errors}")
        return {
            'results': all_results,
            'success_count': total_success,
            'error_count': total_errors,
            'total_count': len(documents_data)
        }
