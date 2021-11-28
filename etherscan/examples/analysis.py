from etherscan import Client


def main():
    ohm = "0x383518188c0c6d7730d91b2c03a03c837814a899"
    client = Client()
    approvals = client.get_transaction_history_by_address(ohm, start="11/25/2021")
    for approval in approvals:
        for tx in client.accounts.get_transactions_by_address(
            approval["from"],
            start_block=approval["blockNumber"],
            end_block=client.blocks.latest_block,
        ):
            if tx["to"] == approval["to"]:
                print(tx)
