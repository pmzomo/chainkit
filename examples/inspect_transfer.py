"""Build a USDC transfer and check exactly what it does before signing. Runs offline (no RPC needed).

    python examples/inspect_transfer.py
"""
from solders.hash import Hash
from solders.keypair import Keypair
from solders.transaction import Transaction

from chainkit.amounts import format_usdc, to_atomic
from chainkit.constants import usdc_mint
from chainkit.transactions import TransferPlan, build_transfer_message, describe_message, transaction_size


def main() -> None:
    fee_payer, sender, recipient = Keypair(), Keypair(), Keypair()
    mint = usdc_mint('devnet')
    amount = to_atomic('12.50')

    plan = TransferPlan(fee_payer=str(fee_payer.pubkey()), source_owner=str(sender.pubkey()), mint=mint,
                        amount=amount, destination_owner=str(recipient.pubkey()), memo='invoice 1042')
    recent_blockhash = str(Hash.new_unique())  # in real use: rpc.latest_blockhash()[0]
    message = build_transfer_message(plan, recent_blockhash)

    facts = describe_message(message)
    print('fee payer      ', facts.fee_payer)
    print('signers        ', facts.signers)
    print('compute units  ', facts.compute_unit_limit)
    for transfer in facts.transfers:
        print('transfer       ', format_usdc(transfer['amount']), 'USDC', transfer['source'], '->',
              transfer['destination'])
    for created in facts.ata_creations:
        print('creates account', created['ata'], 'for', created['owner'], 'paid by', created['payer'])
    print('memos          ', facts.memos)
    print('unrecognised   ', facts.unknown or 'nothing')

    # Refuse to sign anything that is not exactly what was intended.
    if not facts.is_clean or [t['amount'] for t in facts.transfers] != [amount]:
        raise SystemExit('Refusing to sign: the transaction does not match the intent.')

    transaction = Transaction([fee_payer, sender], message, message.recent_blockhash)
    print('signed, size   ', transaction_size(message), 'bytes; signature', transaction.signatures[0])


if __name__ == '__main__':
    main()
