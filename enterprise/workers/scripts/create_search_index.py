"""Create/update the per-agency policy RAG index in Azure AI Search (SCOPING §7).

The index schema is the contract between the ingestion worker (writer,
`consumers/ingestion.py`) and the finance approver (reader, `rag/retriever.py`):

  - `agency_id`  filterable — the mandatory security-trimming field (agency isolation).
  - `policy_version`         — pins the version a decision was made against (reproducibility).
  - `content`    searchable  — the clause text the LLM is judged against.
  - `content_vector`         — embeddings (text-embedding-3-large → 3072 dims) for hybrid search.
  - semantic config named `default` — the name AzureSearchRetriever requests.

Run once per environment (idempotent):

    WORKERS_SEARCH_ENDPOINT=https://<svc>.search.windows.net \
    python -m workers.scripts.create_search_index           # Managed Identity
    #   or pass --api-key for local dev

Needs the `[azure]` extra (azure-search-documents, azure-identity).
"""

from __future__ import annotations

import argparse
import sys

from workers.config import load_settings

# Dimensions for the embedding model deployed in Foundry (infra/modules/ai.bicep).
_EMBED_DIMS = 3072  # text-embedding-3-large
_VECTOR_PROFILE = "policy-hnsw"
_SEMANTIC_CONFIG = "default"  # must match AzureSearchRetriever(semantic_config=...)


def build_index(name: str):
    """Build the SearchIndex definition (lazy Azure imports)."""
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
        SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=_EMBED_DIMS,
            vector_search_profile_name=_VECTOR_PROFILE,
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="policy-hnsw-algo")],
        profiles=[
            VectorSearchProfile(
                name=_VECTOR_PROFILE, algorithm_configuration_name="policy-hnsw-algo"
            )
        ],
    )
    semantic = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name=_SEMANTIC_CONFIG,
                prioritized_fields=SemanticPrioritizedFields(
                    content_fields=[SemanticField(field_name="content")]
                ),
            )
        ]
    )
    return SearchIndex(
        name=name, fields=fields, vector_search=vector_search, semantic_search=semantic
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Provision the policy RAG index.")
    parser.add_argument("--api-key", default=None, help="admin key (local dev; prefer MI)")
    args = parser.parse_args(argv)

    settings = load_settings()
    if not settings.search_endpoint:
        print("WORKERS_SEARCH_ENDPOINT is not set.", file=sys.stderr)
        return 2

    from azure.search.documents.indexes import SearchIndexClient  # noqa: PLC0415

    if args.api_key:
        from azure.core.credentials import AzureKeyCredential  # noqa: PLC0415

        credential = AzureKeyCredential(args.api_key)
    else:
        from azure.identity import DefaultAzureCredential  # noqa: PLC0415

        credential = DefaultAzureCredential()

    client = SearchIndexClient(endpoint=settings.search_endpoint, credential=credential)
    index = build_index(settings.search_index_name)
    client.create_or_update_index(index)
    print(f"Index '{settings.search_index_name}' created/updated at {settings.search_endpoint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
