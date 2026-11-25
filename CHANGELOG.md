# Changelog

All notable changes are listed here. The project follows [Semantic Versioning](https://semver.org/).

## 0.1.0 (2026-11-25)

First public release, extracted from GT Pay.

- `amounts`: exact USDC amounts as integer atomic units; rejects floats, plain integers, scientific notation,
  malformed thousands separators, more than 6 decimals and values above u64.
- `addresses`: strict address parsing, associated token account derivation.
- `instructions`: range-checked transferChecked, createIdempotent, compute budget and memo.
- `transactions`: `TransferPlan`, `build_transfer_message`, `describe_message` with compute budget facts and
  `is_clean`, `transaction_size`.
- `parse`: balance-delta deposit detection (`usdc_delta`, `owner_delta`, `senders`), including closed accounts and
  ignoring failed transactions and other token programs.
- `rpc`: JSON-RPC client with ordered failover, transient error signalling, complete paging (raises instead of
  truncating) and rent queries.
- `pyth`: verified Pyth price read directly from Solana (owner, verification level, feed id, age, confidence).
