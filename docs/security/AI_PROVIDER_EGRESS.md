# AI provider egress policy

PARTHA treats an AI provider destination as a deployment security boundary. A
tenant may choose from the supported providers and supply their own provider
credential, but a tenant cannot expand the set of network destinations the API
is allowed to contact.

This document describes the application control. It does **not** replace a
production network egress control.

## Safe default and modes

`AI_EGRESS_MODE` defaults to `hosted`. This is deliberately fail-safe in every
environment, including when deployment configuration is incomplete.

| Mode | Fixed cloud providers | Configurable Ollama endpoint |
| --- | --- | --- |
| `hosted` | Only their code-owned HTTPS origins are accepted; each DNS answer must be public unicast. | Requires an exact administrator-owned base URL in `AI_EGRESS_ALLOWED_BASE_URLS`; every DNS answer must be public unicast. |
| `self_hosted` | Only their code-owned HTTPS origins are accepted; each DNS answer must be public unicast. | Requires both an exact administrator-owned base URL and that every current DNS answer is within `AI_EGRESS_ALLOWED_CIDRS`. This is the only mode for a local or internal endpoint. |

There are no wildcard hosts, wildcard paths, tenant-supplied CIDRs, or fallback
local endpoints. Built-in OpenAI, Anthropic, Gemini, and OpenRouter requests do
not accept a `baseUrl` at all.

## Configuration

All three values are deployment-owned environment settings:

```dotenv
AI_EGRESS_MODE=self_hosted
AI_EGRESS_ALLOWED_BASE_URLS=http://ollama.example:11434
AI_EGRESS_ALLOWED_CIDRS=192.0.2.0/24
```

Use a comma-separated list if more than one administrator-approved endpoint or
network is required. Base URLs are compared after safe normalization of scheme,
IDNA hostname, one trailing DNS dot, default port, and trailing base-path slash.
The request must still be under that exact normalized base path.

The settings parser rejects an invalid mode, malformed URL, malformed CIDR,
credentials in a URL, fragments, non-HTTP(S) scheme, missing host, ambiguous
host spelling, invalid port, and ambiguous path encoding. A bad policy setting
prevents startup rather than weakening the policy.

For a local Ollama installation, use `self_hosted`, an exact local base URL, and
the smallest matching CIDR. Do not expose these values in tenant-facing forms,
and do not add a wildcard so users can route the API to arbitrary hosts.

## Enforcement lifecycle

The policy runs twice:

1. `PUT /ai/config` validates a configurable base URL and its current DNS
   answers before the provider configuration record is created or changed. A
   denial is the normal `422 validation_error` response and leaves the existing
   record untouched.
2. The common provider sender validates again immediately before every outbound
   request. This covers `/ai/test` and `/ai/query`, including
   configurations saved before this feature existed.

At request time PARTHA resolves the original hostname, validates **every**
answer, then connects HTTPX to one validated IP literal. The original `Host`
header and HTTPS SNI hostname are retained, so TLS certificate validation stays
enabled while the HTTP client has no reason to look up the original hostname a
second time. Environment proxy variables are ignored for provider traffic, and
connection retries are disabled so a failed request returns through the policy
boundary and the next request performs a fresh validation and pin.

If resolution returns no answers, an invalid answer, or a mixture of permitted
and disallowed answers, the request is denied. If DNS changes after a valid
save, the request-time check blocks it before the transport is invoked.

Hosted mode permits public unicast answers only. Multicast, unspecified,
reserved, loopback, private, link-local, shared/non-global, scoped IPv6, and
IPv4-mapped forms of those classes are denied. Self-hosted mode may admit
private or loopback unicast only through an exact URL and matching explicit
CIDR; non-unicast, link-local, reserved, scoped, and ambiguous/shared classes
remain denied even if an administrator supplies a broad CIDR.

Provider requests explicitly disable redirect following. Any 3xx response is a
controlled provider failure; PARTHA never sends a request to its `Location`
target.

Policy errors use a generic message. Normal API errors and logs must not include
the rejected URL, hostname, resolved addresses, or any URL credentials. Gemini
credentials are sent in the provider-supported API-key header rather than the
query string, and HTTPX/httpcore request-detail logging is held at warning level
even when application debug logging is enabled.

## Existing configuration migration

No migration deletes or rewrites existing provider configurations. A previously
stored endpoint that does not comply with the current deployment policy remains
in the database but cannot be used at request time. An administrator or user
must replace it with a policy-compliant configuration before it can run.
Because configurable Ollama destinations are also resolved when saved, a
transient DNS failure rejects the save without changing the existing record;
retry after name resolution is healthy.

## Production network controls

A hosted or shared deployment needs a deployment-level firewall, cloud egress
rule, service-mesh policy, or approved egress proxy that:

- denies unapproved private, loopback, link-local, and external destinations;
- permits only the approved provider traffic; and
- is reviewed together with the application allowlist and DNS assumptions.

Application URL validation is defence in depth, not a replacement for network
enforcement. This repository does not provide Kubernetes manifests, so no
Kubernetes policy is implied by this document.

## Rollout and verification checklist

Before enabling AI providers in a hosted or shared deployment:

1. Keep `AI_EGRESS_MODE=hosted` unless a trusted administrator truly needs a
   self-hosted endpoint.
2. For self-hosted mode, record the exact base URLs and smallest CIDRs in the
   deployment secret/configuration system; do not let tenants edit them.
3. Apply and test a network egress control independently of the application.
4. Run the focused provider egress regression suite and the full backend suite.
5. Test an approved provider configuration and verify a disallowed or stale
   configuration produces the generic validation error without a network call.
6. Confirm redirects are reported as provider failures and no policy details
   appear in logs or API responses.

See the root and backend environment examples for the supported variables.
