import uuid

def octa_word_paymant_suffix() -> str:
    suffix_string = str(uuid.uuid4().hex[:8].upper())
    return suffix_string

def generate_payment_id(payment_mode: str) -> str:
    """Generate a payment ID based on the payment mode."""
    suffix_string = octa_word_paymant_suffix()
    return f"{payment_mode.upper()}_{suffix_string}"