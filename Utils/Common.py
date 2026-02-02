def parse_bool(value):
    """Converte strings e outros tipos para booleano de forma segura."""
    if isinstance(value, bool): return value
    if isinstance(value, str): return value.lower() in ('true', '1', 't', 's', 'sim')
    return bool(value)