"""Create/update the per-agency policy index in Azure AI Search (SCOPING §7).

Bicep provisions the search *service*; the index *schema* is created here (one-time, or
whenever the schema changes). Fields match exactly what the ingestion pipeline upserts
(`workers.consumers.ingestion.upsert_to_search`):

    id            key
    agency_id     FILTERABLE  ← the security-trimming boundary (per-department isolation)
    policy_version FILTERABLE/retrievable ← version pinning (SCOPING §7)
    chunk_index   retrievable
    content       SEARCHABLE  ← keyword + semantic ranking
    content_vector vector     ← hybrid (vector) retrieval

Run:  python -m workers.rag.index_setup        (uses WORKERS_* env / .env)
Auth: Managed Identity (DefaultAzureCredential) preferred; WORKERS_SEARCH_API_KEY for
      local dev. The identity needs the "Search Service Contributor" role.
"""

from __future__ import annotations

import logging

from workers.config import Settings, load_settings

logger = logging.getLogger(__name__)

# text-embedding-3-large = 3072 dims; change if you pin a different embedding model.
_VECTOR_DIMS = 3072


def build_index(index_name: str):
    """Construct the SearchIndex definition (lazy-imports the Azure SDK models)."""
    from azure.search.documents.indexes.models import (  # noqa: PLC0415
        HnswAlgorithmConfiguration,
        SearchableField,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SemanticConfiguration,
        SemanticField,
        SemanticPrioritizedFields,
        SemanticSearch,
        SimpleField,
        VectorSearch,
        VectorSearchProfile,
    )

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="agency_id", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="policy_version", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="chunk_index", type=SearchFieldDataType.Int32),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=_VECTOR_DIMS,
            vector_search_profile_name="default-profile",
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="default-hnsw")],
        profiles=[VectorSearchProfile(name="default-profile", algorithm_configuration_name="default-hnsw")],
    )

    # Semantic ranker config named "default" — the retriever asks for this by name.
    semantic = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name="default",
                prioritized_fields=SemanticPrioritizedFields(
                    content_fields=[SemanticField(field_name="content")]
                ),
            )
        ]
    )

    return SearchIndex(
        name=index_name, fields=fields, vector_search=vector_search, semantic_search=semantic
    )


def create_policy_index(settings: Settings | None = None, *, recreate: bool = False) -> str:
    """Create or update the index. Returns the index name.

    Some index properties (notably the vector-search algorithm name) are immutable —
    Azure AI Search rejects an update that changes them. Pass `recreate=True` to drop and
    recreate the index instead. Safe in dev (the index holds only re-seedable policy chunks);
    in prod, prefer a new index name + reindex rather than dropping live data.
    """
    settings = settings or load_settings()
    if not settings.search_endpoint:
        raise RuntimeError("WORKERS_SEARCH_ENDPOINT is not set — cannot create the index.")

    from azure.search.documents.indexes import SearchIndexClient  # noqa: PLC0415

    if settings.search_api_key:
        from azure.core.credentials import AzureKeyCredential  # noqa: PLC0415

        credential = AzureKeyCredential(settings.search_api_key)
    else:
        from azure.identity import DefaultAzureCredential  # noqa: PLC0415

        credential = DefaultAzureCredential()

    client = SearchIndexClient(endpoint=settings.search_endpoint, credential=credential)

    if recreate:
        try:
            client.delete_index(settings.search_index_name)
            logger.info("Deleted existing index '%s' for recreate", settings.search_index_name)
        except Exception:  # noqa: BLE001 - fine if it doesn't exist yet
            logger.info("No existing index to delete (or delete failed harmlessly)")

    index = build_index(settings.search_index_name)
    client.create_or_update_index(index)
    logger.info("Created/updated index '%s' on %s", settings.search_index_name, settings.search_endpoint)
    return settings.search_index_name


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    recreate = "--recreate" in sys.argv
    name = create_policy_index(recreate=recreate)
    print(f"Index ready: {name}")
