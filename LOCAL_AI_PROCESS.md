# Local AI briefing — 22 October 2026

Owner sidebar: Local AI briefing (/ai-briefing/ or /station2/ai-briefing/). Choose business date, both organisations or current organisation only, and English or Hindi. Generate on demand. Model: Qwen3 1.7B; runner: CPU-only Ollama packaged from the official Alpine Linux repository. Model weights are downloaded from Ollama's model registry. This PC has 16 GB RAM; the container is limited to 4 GB RAM and two CPUs.

## What it does
The software computes factual day status and a list of verified checks: missing shift records, missing opening accounts, negative balances, pending digital settlements, stock exceptions, shortages and estimated older debt. The local model ranks up to three existing check IDs. A JSON schema and server-side validation reject invented IDs, duplicate IDs, unfinished output and invalid responses. Displayed facts and check wording come from deterministic application rules, not free-form model claims. All verified checks remain available below the AI priorities.

The first unrestricted narration test invented missing accounts/incomplete days. That design was rejected and replaced by the constrained prioritisation workflow. This is AI-assisted prioritisation, not an unrestricted chatbot, financial decision maker, accounting engine or forecast. Its priority order can still be imperfect. Source figures and all checks remain available for owner review. No changes, tools, database writes, transfers, deductions or tax actions are available to the model.

## Privacy and isolation
Cloud features are disabled with OLLAMA_NO_CLOUD=1. Ollama has only the internal ai_private Docker network, no default internet route, and no host port mapping. Web services contact its fixed Docker URL. The application rejects an alternate/cloud endpoint or unapproved model. There is no cloud fallback. Inputs contain verified check descriptions and selected amounts, not employee/customer details, free-form business notes, credentials, files or external documents. Briefings are not stored by the app in business records or browser local storage; they remain visible in the page while open. Responses are private/no-store. The model has no access to the station database volumes.

## Setup and recovery
From this project folder in PowerShell: ./setup-local-ai.ps1. It temporarily attaches the Ollama service to the default Docker network solely to download qwen3:1.7b, then removes the download override in a finally block and starts normal services. Normal operation uses compose.yaml alone. Check docker compose -p hpcl_pump -f compose.yaml exec -T ollama ollama list. Weights persist in hpcl_pump_local_ai_models. Normal encrypted business backups do not include the 1.4 GB model weights: they can be downloaded again; copy the model volume separately if offline recovery is required.

Internet is required to obtain packages and model weights, not for local inference after setup. Do not leave compose.ai-download.yaml active for normal operation. If download isolation restart fails, stop AI and restore the base Compose configuration before use. Never expose Ollama directly on the LAN. Disabling AI does not remove normal manual station workflows.

## Verification
146 automated tests passed. Eight AI tests cover owner-only access, validated forms, excluded sensitive/free-form fields, local endpoint/model restriction, no tools, escaped display, timeout and concurrent generation handling, unavailable requested station, invented/duplicate check rejection and completed-day rule correctness. The full app suite and station checks pass. Runtime network inspection confirms an internal-only Ollama network with no default route and no port mapping. Real local model generation was tested on synthetic 19 October records; browser verification covers both organisations and English/Hindi. AI does not replace record review, and this remains a local prototype, not production-ready.

References: https://docs.ollama.com/api/chat ; https://docs.ollama.com/faq ; https://pkgs.alpinelinux.org/package/v3.23/community/x86_64/ollama ; https://ollama.com/library/qwen3:1.7b
