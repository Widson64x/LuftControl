# Utils/hash_utils.py
import hashlib
from datetime import datetime

def gerar_hash(row):
    """
    Gera um hash único para a linha.
    Implementação BASE do sistema (Origem: Routes/Adjustments.py).
    
    Regras:
    1. Chave: Origem + Filial + Numero + Item + Conta + Data
    2. Strings limpas (strip), None vira 'None'
    3. Data formatada estritamente YYYY-MM-DD
    
    Suporta: dict e objetos SQLAlchemy.
    """
    def get_val(obj, key):
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    def clean(val):
        if val is None: return 'None'
        s = str(val).strip()
        return 'None' if s == '' or s.lower() == 'none' else s

    # Tratamento específico para Data
    dt_val = get_val(row, 'Data')
    dt_str = 'None'
    
    if dt_val:
        # Se for objeto datetime/date
        if hasattr(dt_val, 'strftime'):
            dt_str = dt_val.strftime('%Y-%m-%d')
        # Se for string (ex: '2025-11-26 00:00:00')
        else:
            s_dt = str(dt_val).strip()
            if ' ' in s_dt: s_dt = s_dt.split(' ')[0] # Pega só a data
            if 'T' in s_dt: s_dt = s_dt.split('T')[0]
            dt_str = s_dt

    # Recupera valores usando as chaves padrão do sistema
    # Nota: Tenta 'origem' (minúsculo) e 'Origem' (Maiúsculo) para compatibilidade
    origem = clean(get_val(row, 'origem') or get_val(row, 'Origem'))
    filial = clean(get_val(row, 'Filial'))
    numero = clean(get_val(row, 'Numero'))
    item = clean(get_val(row, 'Item'))
    conta = clean(get_val(row, 'Conta'))
    
    # Montagem da String Raw (Padrão Adjustments.py)
    raw = f"{origem}-{filial}-{numero}-{item}-{conta}-{dt_str}"
    
    return hashlib.md5(raw.encode('utf-8')).hexdigest()