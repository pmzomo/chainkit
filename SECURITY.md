# Security policy

chainkit sits on the payment path, so we treat security reports as the highest priority.

## Reporting a vulnerability

Please do **not** open a public issue. Email **support@gtbai.co** with the subject "chainkit security", a description,
and steps to reproduce. We acknowledge within 3 business days and aim to release a fix within 14 days for serious
issues, crediting you unless you prefer otherwise.

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | Yes |

## Scope

In scope: incorrect amount handling, a look-alike token being treated as USDC, `describe_message` failing to report an
instruction, address parsing accepting invalid input, Pyth validation that can be bypassed. chainkit never handles
private keys; key storage and signing are the caller's responsibility.
