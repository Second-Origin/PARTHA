# Connecting an AI provider

PARTHA works fully without an AI provider. Extraction, the sealed `ri.v1`
snapshot, Architecture, Dependencies, Repository Insights, and Engineering
Review are all deterministic and provider-free. A provider is only needed for
the free-form **AI workspace** ("ask about this repository"), which sends the
provider *structural context only* — module roles, dependency names, finding
titles, selected file paths — never source bytes or line spans.

Provider configuration is **per user** and stored by your own backend. The API
key is Fernet-encrypted at rest and never returned in full (only its last four
characters). One provider configuration is active at a time; saving a new one
replaces the previous.

## The supported providers

| Provider | Needs API key | Needs base URL | Default model | Where the key comes from |
| --- | --- | --- | --- | --- |
| OpenAI | yes | no | `gpt-4o-mini` | <https://platform.openai.com/api-keys> |
| Anthropic | yes | no | `claude-3-5-haiku-latest` | <https://console.anthropic.com/settings/keys> |
| Google Gemini | yes | no | `gemini-1.5-flash` | <https://aistudio.google.com/apikey> |
| OpenRouter | yes | no | `openai/gpt-4o-mini` | <https://openrouter.ai/keys> |
| Ollama | no | **yes** | `llama3.2` | runs on a machine you control |

This table is generated in code from one source
(`apps/backend/app/ai/providers/capabilities.py`) and served at
`GET /ai/providers`; the Settings UI renders it rather than hardcoding it, so it
never drifts from what the save/test flow actually requires.

The four hosted providers reach only their own code-owned HTTPS origins and do
**not** accept a base URL. Only Ollama has a configurable endpoint, and that
endpoint is governed by the deployment's egress policy — see
[Before you start: Ollama and any custom endpoint](#before-you-start-ollama-and-any-custom-endpoint).

## The recommended way: Settings → AI Providers

1. Sign in, open **Settings**, and select the **AI Providers** tab.
2. Click the provider you want. The panel shows that provider's short setup
   checklist and a link to its official key page.
3. Fill in what the provider needs:
   - **Provider model ID** — pre-filled with the default above; change it only
     if you want a specific model. A model the provider does not recognise is
     the most common cause of a failed request.
   - **Base URL** — Ollama only. The origin where Ollama is listening, e.g.
     `http://localhost:11434`. No trailing path.
   - **API key** — the hosted providers. Pasted once; after saving, the field
     shows `•••• 1234` and an empty save keeps the stored key.
4. Click **Test Connection**. This sends one real request through the same
   egress policy and transport a live query uses, and reports back in plain
   language without storing anything. Fix any error before saving.
5. Click **Save Provider**. The status pill changes to `Saved: <provider>`.
6. Open the AI workspace for an analysed repository and ask a question.

### The same flow over the API

| Step | Call |
| --- | --- |
| List providers and their requirements | `GET /ai/providers` |
| Read current config (no secret) | `GET /ai/config` |
| Save / replace config | `PUT /ai/config` with `{ "provider", "apiKey?", "model?", "baseUrl?" }` |
| Test without saving | `POST /ai/test` with the same shape (omit `apiKey` to test the stored one) |
| Ask a question | `POST /ai/query` with `{ "repositoryId", "query", "context?" }` |

Every `ai/*` route requires authentication and is owner-scoped: a query can
never run against another user's repository or spend their key.

## Before you start: Ollama and any custom endpoint

The four hosted providers work in every environment with just a key. **A
configurable Ollama base URL additionally requires deployment configuration**,
because PARTHA treats an outbound AI destination as a security boundary:

- `AI_EGRESS_MODE` defaults to `hosted`. In that mode an Ollama base URL is
  accepted only if it exactly matches an entry in `AI_EGRESS_ALLOWED_BASE_URLS`
  and every DNS answer for it is public unicast.
- A **local or private-network** Ollama (`localhost`, `127.0.0.1`, a
  `192.168.x.x` box) needs `AI_EGRESS_MODE=self_hosted`, an exact
  `AI_EGRESS_ALLOWED_BASE_URLS` entry, and a matching `AI_EGRESS_ALLOWED_CIDRS`
  range.

```dotenv
AI_EGRESS_MODE=self_hosted
AI_EGRESS_ALLOWED_BASE_URLS=http://localhost:11434
AI_EGRESS_ALLOWED_CIDRS=127.0.0.1/32
```

These are deployment-owned environment settings, not user form fields. A bad
value stops the backend from starting rather than weakening the policy. The
policy is enforced twice — once when the config is saved (a bad URL is a normal
`422`, and the existing record is left untouched) and again immediately before
every outbound request. The full rules, including how DNS is pinned and how
redirects are handled, are in the
[AI provider egress policy](../security/AI_PROVIDER_EGRESS.md); read it before
configuring any custom or local endpoint.

## Ollama specifics

Ollama runs inference on the machine you point it at, so its behaviour differs
from a hosted API in ways worth knowing:

- **The first request after startup is slow.** Ollama loads the model into
  memory before generating a single token. A review-sized prompt on CPU can
  take minutes. PARTHA allows a long read budget for Ollama (a tight 10s
  connect so a wrong URL fails fast, then up to 10 minutes for the response) so
  a slow-but-healthy generation is not cut off. Hosted providers keep a 60s
  timeout.
- **One request at a time.** PARTHA serialises its own requests to Ollama;
  additional requests queue rather than fail. Ollama already serialises token
  generation by default, so more concurrency would only raise memory pressure
  without finishing anything sooner.
- **Pull the model first.** `ollama pull llama3.2` (or whichever model ID you
  set) before testing the connection, or the first request fails with an
  "unsupported model" style error.
- **Keep it running.** If Ollama is stopped or the base URL is wrong, the test
  and every query return "Could not reach the AI provider…" within the connect
  timeout.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Save returns `422 validation_error`, "destination is not permitted" | The base URL is not in the deployment allowlist, or the mode is `hosted` for a local endpoint | Set `AI_EGRESS_MODE` / `AI_EGRESS_ALLOWED_BASE_URLS` / `AI_EGRESS_ALLOWED_CIDRS` to match the exact URL, then save again |
| "AI provider rejected the API key" | Wrong, revoked, or expired key | Regenerate the key at the provider and paste it again |
| "AI provider rejected the request… unsupported model ID" | The model ID is not one the provider serves (or not pulled, for Ollama) | Correct the model ID; for Ollama run `ollama pull <model>` |
| "Could not reach the AI provider…" | Self-hosted provider not running, or wrong base URL | Start Ollama; confirm the origin and port |
| "AI provider did not respond in time" (hosted) | Provider slow or overloaded | Retry shortly |
| Query works, answers have no citations | Expected | Free-form answers are intentionally uncited — the provider never receives source content or line numbers |

## What a provider never receives

- Source file contents or line spans.
- Another user's repository, configuration, or key.
- Anything, if `AI_EGRESS_MODE` and the allowlist do not explicitly permit the
  destination.

See also: [AI provider egress policy](../security/AI_PROVIDER_EGRESS.md),
[Backend README → AI Workspace endpoints](../../apps/backend/README.md#ai-workspace-endpoints),
[Repository Intelligence](../architecture/REPOSITORY_INTELLIGENCE.md) for what
"structural context only" means.
