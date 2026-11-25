# chainkit

[![CI](https://github.com/pmzomo/chainkit/actions/workflows/ci.yml/badge.svg)](https://github.com/pmzomo/chainkit/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/solana-chainkit.svg)](https://pypi.org/project/solana-chainkit/)
[![Python](https://img.shields.io/pypi/pyversions/solana-chainkit.svg)](https://pypi.org/project/solana-chainkit/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](https://github.com/pmzomo/chainkit/blob/main/LICENSE)

**Production-grade building blocks for USDC payments on Solana, in Python.**

chainkit packages the parts of a Solana payments backend that are easy to get subtly wrong: exact money amounts,
safe USDC transfers, recognising real USDC (and only real USDC), detecting deposits from any wallet or exchange,
surviving RPC outages, and reading a verified price straight from the Pyth oracle on Solana. It is small, typed,
fully tested, and has two runtime dependencies (`solders`, `requests`).

It was extracted from [GT Pay](https://pay.gtbai.co), a USDC wallet and payroll platform for the global workforce
built by Global TalentBridge AI, where it runs the payment path and the separate signing service.

```bash
pip install solana-chainkit
```

```python
import chainkit
```

## Why it exists

Most Solana payment tooling is TypeScript. Python runs a large share of fintech back offices, payroll systems and data
teams, and they need the same guarantees:

| Mistake teams make | What chainkit does |
|---|---|
| Storing money as floats (`0.1 + 0.2`) | Amounts are integer atomic units; floats and ambiguous integers are refused |
| Trusting a token called "USDC" | Compares Circle's exact mint addresses and the classic token program on every balance row |
| Typos in hard-coded addresses | Weekly live tests check the mints, genesis hashes and Pyth account against real Solana |
| Signing whatever transaction a library built | `describe_message` decodes a message into plain facts and lists anything unrecognised, so you can refuse to sign it |
| Missing deposits sent by exchanges or contracts | Detects payments from balance deltas, which works no matter which program moved the funds |
| One RPC provider down means payments stop | Ordered failover across providers, with errors marked transient or final |
| Trusting a price API you do not control | Reads Pyth's price account on Solana and checks owner, verification level, feed id, age and confidence |
| Re-signing a dropped transaction too early (double pay) | Exposes `lastValidBlockHeight` so you only re-sign after the old one can no longer land |

## Quick start

### Exact amounts

```python
from chainkit.amounts import to_atomic, format_usdc

to_atomic('150.25')      # 150250000
to_atomic('1,250.50')    # 1250500000
format_usdc(150250000)   # '150.25'
to_atomic(0.1)           # AmountError: floats are not accepted for money
to_atomic('1e3')         # AmountError: scientific notation is not an amount
```

### Detect a USDC deposit (from any wallet or exchange)

```python
from chainkit.constants import usdc_mint
from chainkit.addresses import derive_ata
from chainkit.parse import usdc_delta, senders
from chainkit.rpc import SolanaRpc

rpc = SolanaRpc(['https://api.devnet.solana.com'])   # add a second provider for failover
mint = usdc_mint('devnet')
token_account = str(derive_ata('YourWalletAddress...', mint))

for item in rpc.signatures_for_address(token_account, limit=20):
    tx = rpc.transaction(item['signature'])          # finalized by default
    received = usdc_delta(tx, token_account, mint)    # atomic units; 0 for failed tx or look-alike tokens
    if received > 0:
        print(item['signature'], received, 'from', senders(tx, mint))
```

### Build a transfer, then check it before signing

```python
import base64

from solders.transaction import Transaction
from chainkit.transactions import TransferPlan, build_transfer_message, describe_message

plan = TransferPlan(fee_payer=str(payer.pubkey()), source_owner=str(owner.pubkey()), mint=mint,
                    amount=5_000_000, destination_owner='RecipientWallet...', memo='invoice 1042')
blockhash, last_valid_height = rpc.latest_blockhash()
message = build_transfer_message(plan, blockhash)

facts = describe_message(message)            # what will this transaction actually do?
assert facts.is_clean                        # nothing unrecognised
assert facts.transfers[0]['amount'] == 5_000_000

tx = Transaction([payer, owner], message, message.recent_blockhash)
signature = rpc.send_transaction(base64.b64encode(bytes(tx)).decode())
# Only build and sign a replacement once block height > last_valid_height and the signature was never seen.
```

If the recipient has no USDC account yet, the plan adds an idempotent account creation paid by `fee_payer`. The
one-time rent for that account is `rpc.minimum_balance_for_rent_exemption(165)` lamports. Query it: rent is not a
constant (it fell from 2,039,280 to 1,488,440 lamports by November 2026).

### Verified SOL/USD price from Pyth, read on-chain

```python
from chainkit import pyth
from chainkit.rpc import SolanaRpc

price = pyth.read_price(SolanaRpc(['https://api.mainnet-beta.solana.com']))
print(price.price, '+/-', price.conf)    # Decimal('72.70629150') +/- Decimal('0.02...')
```

`read_price` refuses the account unless it is owned by the Pyth Solana Receiver program, fully verified by Wormhole
guardians, the SOL/USD feed, at most 5 minutes old and within a 2% confidence band. Any Pyth feed works by passing its
price account and feed id.

More in [`examples/`](https://github.com/pmzomo/chainkit/tree/main/examples):

| Example | Network |
|---|---|
| `inspect_transfer.py`: build a transfer, inspect it, refuse unless it matches the intent, sign | Offline |
| `detect_deposits.py`: list recent USDC deposits to a wallet from any sender | Devnet or mainnet |
| `account_setup_cost.py`: live rent plus Pyth price = USD cost of creating a recipient's USDC account | Mainnet |

## Modules

| Module | Purpose |
|---|---|
| `chainkit.constants` | Program ids, cluster genesis hashes, Circle's USDC mints, `cluster_for_genesis` |
| `chainkit.amounts` | `to_atomic`, `from_atomic`, `format_usdc` |
| `chainkit.addresses` | Strict `parse_pubkey`, `derive_ata`, `is_on_curve` |
| `chainkit.instructions` | Range-checked `transfer_checked`, `create_ata_idempotent`, compute budget, `memo` |
| `chainkit.transactions` | `TransferPlan`, `build_transfer_message`, `describe_message` (`MessageFacts`), `transaction_size` |
| `chainkit.parse` | `usdc_delta`, `owner_delta`, `senders`, `fee_lamports` |
| `chainkit.rpc` | `SolanaRpc` with failover; `RpcError(code, transient)`; typed helpers incl. paging and rent |
| `chainkit.pyth` | `read_price`, `parse_price_update`, SOL/USD constants |

## Safety model

- **Exact assets only.** USDC is identified by mint address and token program, never by name. Token-2022 rows with a
  USDC-looking mint are ignored.
- **Allowlisted instructions.** Built transfers use only compute budget, idempotent token-account creation,
  `transferChecked` and memo. `describe_message` reports anything else in `unknown`.
- **Fail loudly.** Invalid amounts, addresses, out-of-range integers and oversized transactions raise immediately;
  paging that would be incomplete raises instead of returning a partial list.
- **Know your cluster.** Compare `rpc.genesis_hash()` with `constants.genesis_hash(cluster)` before signing, so a
  mainnet key never signs against the wrong network (and the reverse).
- **No keys inside.** chainkit never stores, generates or transmits private keys. You sign with your own signer
  (solders `Keypair`, a KMS, an HSM).

## Scope

chainkit builds and reads **legacy** messages and the **classic SPL Token** program, which is what USDC uses. It is a
library, not a wallet or a custody service. Deposit detection reads `jsonParsed` transactions; pair it with your own
storage of the last processed signature.

## Development

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest --cov                                       # unit tests, no network
CHAINKIT_LIVE=1 pytest -m live                     # optional: checks against public Solana RPC and Pyth
ruff check . && mypy
```

## Documentation

The full system specification, with diagrams of every flow, is in
[docs/SPECIFICATION.md](https://github.com/pmzomo/chainkit/blob/main/docs/SPECIFICATION.md).

## Status

Version 0.1.0, beta. The API may still change before 1.0; changes are listed in [CHANGELOG.md](https://github.com/pmzomo/chainkit/blob/main/CHANGELOG.md).
Security issues: see [SECURITY.md](https://github.com/pmzomo/chainkit/blob/main/SECURITY.md).

## License

Apache License 2.0. Copyright 2026 Global TalentBridge AI LLC. See [LICENSE](https://github.com/pmzomo/chainkit/blob/main/LICENSE) and [NOTICE](https://github.com/pmzomo/chainkit/blob/main/NOTICE).
