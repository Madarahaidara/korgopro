def get_customer_full_name(customer):
    """Retourne le nom complet du client"""
    if not customer:
        return ""
    
    full_name = f"{customer.first_name or ''} {customer.last_name or ''}".strip()
    if customer.company:
        if full_name:
            return f"{full_name} ({customer.company})"
        else:
            return customer.company
    return full_name if full_name else f"Client #{customer.id}"