def process_payment(amount, method="SANDBOX"):
    """
    Simulate a payment process.
    """
    return {
        "status": "SUCCESS",
        "transaction_id": "SANDBOX_TXN_12345",
        "method": method,
        "amount": amount
    }
