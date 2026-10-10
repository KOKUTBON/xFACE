# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.0.x   | :white_check_mark: |
| < 2.0   | :x:                |

## Reporting a Vulnerability

xFACE handles biometric data and controls physical doors, so security reports are taken seriously.

1. **Do not open a public issue** for a vulnerability.
2. Report it privately through [GitHub Security Advisories](https://github.com/KOKUTBON/xFACE/security/advisories/new).
3. Include reproduction steps, a proof of concept if possible, and the affected version.

You will get an acknowledgement as soon as possible, and a fix and disclosure timeline will be agreed with you.

## Deployment Checklist

xFACE ships in a public-safe synthetic demo mode. Before production deployment:

- Set a strong, unique `DASHBOARD_PASSWORD`. If omitted, xFACE creates a random per-install credential in `DATA_DIR/.admin_password` with mode `0600`; there is no universal password.
- Set a random `SECRET_KEY` (`python -c "import secrets; print(secrets.token_hex(32))"`).
- Put xFACE behind HTTPS (reverse proxy such as Caddy, nginx or Traefik). Session cookies are only as safe as the transport.
- Keep `MONITOR_REQUIRE_LOGIN=true` (the secure default). All administration, video, snapshots, logs, relay controls, and recognition controls require an authenticated session.
- Keep CompreFace and the Shelly relay on a private network segment; restrict access to the CompreFace admin UI.
- Choose a `SNAPSHOT_RETENTION_DAYS` value that matches your privacy obligations.
- Set `DEMO_MODE=false` only after configuring and reviewing real biometric and hardware integrations.
- Configure `CORS_ORIGINS` only with explicit trusted origins; wildcards are rejected.

## Threat model

Assume the web server is reachable by an untrusted network user. The application protects administrative routes, relay actions, video, snapshots, enrollment, and recognition controls with session authentication; it does not replace HTTPS, network segmentation, OS hardening, or physical safety controls. A compromised host or CompreFace/Shelly device is outside this application boundary.

## Privacy and retention

Biometric images, derived embeddings, snapshots, and access logs are sensitive personal data. Obtain appropriate consent and lawful basis, minimize collection, use short retention periods, restrict operator access, encrypt backups, and honor deletion requests. Never commit real faces, embeddings, databases, snapshots, logs, camera URLs, relay addresses, credentials, or production configuration. The public repository uses synthetic fixtures and a synthetic demo provider.

## Production-hardening checklist

- Use `DEMO_MODE=false` only in a private, reviewed deployment.
- Set `API_KEY`, `DASHBOARD_PASSWORD`, and `SECRET_KEY` through a secret manager or protected environment.
- Configure a private camera URL and Shelly URL; never place credentials in source, screenshots, issue reports, or logs.
- Run behind TLS, restrict ingress, use a dedicated unprivileged account, and protect `DATA_DIR`.
- Set and periodically review snapshot retention; disable snapshots if they are not required.
- Test authentication, authorization, upload validation, CORS, session behavior, and relay fail-closed behavior before enabling physical access.

## Security Architecture

- **Credential isolation**: the CompreFace API key stays on the server. Face images are proxied through authenticated endpoints.
- **Password handling**: the admin password is hashed with `scrypt` at startup and verified in constant time.
- **Sessions**: `HttpOnly`, `SameSite=Lax` cookies; login redirects are restricted to local paths.
- **Path traversal defense**: snapshot and upload paths are validated against their target directories.
- **Output encoding**: all user-controlled values are HTML-escaped in the web UI.
- **Relay safety**: per-person cooldown prevents repeated triggers; health checks use the read-only `/shelly` endpoint and never the trigger URL.

## Private reporting contact

Email [kokutbon@gmail.com](mailto:kokutbon@gmail.com) with subject `[xFACE] Security report`. Include affected version/commit, reproduction using synthetic data, preconditions and impact. Do not include live credentials or personal data. This mailbox is the fallback while the repository is private or GitHub's reporting form is unavailable.

After publication, prefer [GitHub private vulnerability reporting](https://github.com/KOKUTBON/xFACE/security/advisories/new) when enabled. Acknowledgment and remediation depend on maintainer availability; no response deadline is guaranteed. Coordinate disclosure and fixes privately.
