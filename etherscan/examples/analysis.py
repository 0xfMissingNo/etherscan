from etherscan import Client


def main():
    ohm = "0x383518188c0c6d7730d91b2c03a03c837814a899"
    client = Client()
    return client.get_transaction_history_by_address(ohm)
