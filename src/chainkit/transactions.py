"""Build and inspect USDC transfer transactions.

`build_transfer_message` creates a transfer from a plain plan using only allowlisted instructions.
`describe_message` decodes any legacy message back into plain facts, and lists everything it does not recognise in
`unknown`, so a signer can refuse to sign anything it cannot fully explain:

    facts = describe_message(message)
    if not facts.is_clean or facts.transfers != [expected]:
        raise RefuseToSign(...)
"""
import struct
from dataclasses import dataclass, field
from typing import Any

from solders.hash import Hash
from solders.message import Message
from solders.pubkey import Pubkey

from . import instructions as ix
from .addresses import derive_ata, parse_pubkey
from .constants import (
    ALLOWED_PROGRAMS,
    ATA_PROGRAM,
    COMPUTE_BUDGET_PROGRAM,
    MAX_TRANSACTION_BYTES,
    MEMO_PROGRAM,
    TOKEN_PROGRAM,
    U64_MAX,
    USDC_DECIMALS,
)

DEFAULT_CU_LIMIT = 60_000


@dataclass
class TransferPlan:
    """What to send. Give exactly one destination: an owner wallet (its token account is derived and created if
    needed, paid by `fee_payer`) or an existing token account."""
    fee_payer: str
    source_owner: str
    mint: str
    amount: int                                   # atomic units
    destination_owner: str | None = None
    destination_token_account: str | None = None
    memo: str = ''
    cu_price_micro_lamports: int = 0
    cu_limit: int = DEFAULT_CU_LIMIT
    decimals: int = USDC_DECIMALS

    def destination_account(self) -> str:
        if self.destination_token_account:
            return str(parse_pubkey(self.destination_token_account))
        if not self.destination_owner:
            raise ValueError('Give exactly one of destination_owner or destination_token_account.')
        return str(derive_ata(self.destination_owner, self.mint))


def build_transfer_message(plan: TransferPlan, recent_blockhash: str) -> Message:
    """A legacy message: compute limit, optional priority fee, optional idempotent account creation,
    transferChecked, optional memo. Raises ValueError for an invalid plan or an oversized transaction."""
    if bool(plan.destination_owner) == bool(plan.destination_token_account):
        raise ValueError('Give exactly one of destination_owner or destination_token_account.')
    if isinstance(plan.amount, bool) or not isinstance(plan.amount, int) or not 1 <= plan.amount <= U64_MAX:
        raise ValueError('amount must be a positive integer number of atomic units')
    for name in ('fee_payer', 'source_owner', 'mint'):
        parse_pubkey(getattr(plan, name))
    source_ata = derive_ata(plan.source_owner, plan.mint)
    destination = plan.destination_account()
    if destination == str(source_ata):
        raise ValueError('Source and destination are the same token account.')
    instructions = [ix.set_compute_unit_limit(plan.cu_limit)]
    if plan.cu_price_micro_lamports:
        instructions.append(ix.set_compute_unit_price(plan.cu_price_micro_lamports))
    if plan.destination_owner:
        instructions.append(ix.create_ata_idempotent(plan.fee_payer, destination, plan.destination_owner, plan.mint))
    instructions.append(ix.transfer_checked(source_ata, plan.mint, destination, plan.source_owner, plan.amount,
                                            plan.decimals))
    if plan.memo:
        instructions.append(ix.memo(plan.memo))
    message = Message.new_with_blockhash(instructions, Pubkey.from_string(plan.fee_payer),
                                         Hash.from_string(recent_blockhash))
    if transaction_size(message) > MAX_TRANSACTION_BYTES:
        raise ValueError('Transaction would exceed the Solana size limit.')
    return message


def transaction_size(message: Message) -> int:
    """Serialized size of the signed transaction: signature count, signatures, then the message."""
    signatures = message.header.num_required_signatures
    return len(bytes(message)) + 1 + 64 * signatures


@dataclass
class MessageFacts:
    fee_payer: str
    signers: list[str]
    programs: list[str]
    transfers: list[dict[str, Any]] = field(default_factory=list)  # source, mint, destination, owner, amount, decimals
    ata_creations: list[dict[str, str]] = field(default_factory=list)  # payer, ata, owner, mint
    memos: list[str] = field(default_factory=list)
    compute_unit_limit: int | None = None
    compute_unit_price: int | None = None
    unknown: list[str] = field(default_factory=list)       # anything not recognised; must be empty to sign

    @property
    def is_clean(self) -> bool:
        return not self.unknown


def describe_message(message: Message) -> MessageFacts:
    """Decode a legacy message into facts. Never raises on unexpected content: it reports it in `unknown`."""
    keys = [str(k) for k in message.account_keys]
    signer_count = message.header.num_required_signatures
    facts = MessageFacts(fee_payer=keys[0], signers=keys[:signer_count], programs=[])
    for compiled in message.instructions:
        program = keys[compiled.program_id_index]
        accounts = [keys[i] for i in compiled.accounts]
        data = bytes(compiled.data)
        facts.programs.append(program)
        if program not in ALLOWED_PROGRAMS:
            facts.unknown.append(f'program {program}')
        elif program == TOKEN_PROGRAM:
            if data[:1] == bytes([ix.TRANSFER_CHECKED]) and len(data) == 10 and len(accounts) == 4:
                amount = struct.unpack('<Q', data[1:9])[0]
                facts.transfers.append({'source': accounts[0], 'mint': accounts[1], 'destination': accounts[2],
                                        'owner': accounts[3], 'amount': amount, 'decimals': data[9]})
            else:
                facts.unknown.append('token instruction other than transferChecked')
        elif program == ATA_PROGRAM:
            if data == bytes([ix.ATA_CREATE_IDEMPOTENT]) and len(accounts) == 6:
                facts.ata_creations.append({'payer': accounts[0], 'ata': accounts[1], 'owner': accounts[2],
                                            'mint': accounts[3]})
            else:
                facts.unknown.append('associated token account instruction other than createIdempotent')
        elif program == COMPUTE_BUDGET_PROGRAM:
            if data[:1] == bytes([ix.CU_LIMIT]) and len(data) == 5:
                facts.compute_unit_limit = struct.unpack('<I', data[1:5])[0]
            elif data[:1] == bytes([ix.CU_PRICE]) and len(data) == 9:
                facts.compute_unit_price = struct.unpack('<Q', data[1:9])[0]
            else:
                facts.unknown.append('compute budget instruction other than limit or price')
        elif program == MEMO_PROGRAM:
            facts.memos.append(data.decode('utf-8', errors='replace'))
        else:  # the system program is allowed only as an account of createIdempotent, never invoked directly
            facts.unknown.append(f'direct call to {program}')
    return facts
