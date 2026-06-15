# policy_docs/ — agency policy documents for RAG seeding

One subfolder per agency, **named by the agency's DB id** (`agencies.id`). Each folder holds
the natural-language finance policy the LLM approver reasons over (SCOPING §7, §20.C), plus
an optional `version.txt` (the `policy_version` string, default `v1`).

```
policy_docs/
  <agency_id>/
    version.txt          # optional, e.g. "crispin-2026.06"
    wifi.md              # any number of .md / .txt files
    travel.md
```

## Get the real agency ids

The folder name is the **security-trimming key** — it must equal the agency_id used at
decision time. After seeding agencies (via `POST /admin/agencies` or the dev seed):

```bash
curl -s localhost:8000/admin/agencies -H "Authorization: Bearer $ADMIN" | jq '.[] | {id, name}'
```

Rename the example folders below to those ids before seeding against Azure.

## Seed

```bash
# 1. create the index (one-time)
python -m workers.rag.index_setup
# 2. load the docs
python workers/scripts/seed_policies.py ./policy_docs
```

With no `WORKERS_SEARCH_ENDPOINT` set, the seed runs in **offline dry-run** and just prints
what it would upsert — safe for checking your layout first.
