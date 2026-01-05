# Reports/Shared/Utils.py
import hashlib
from datetime import datetime

class ReportUtils:
    @staticmethod
    def aplicar_escala_milhares(data_rows, colunas_meses):
        """Divide valores monetários por 1000 nas colunas especificadas."""
        for row in data_rows:
            for col in colunas_meses:
                val = row.get(col)
                if val is not None and isinstance(val, (int, float)):
                    row[col] = val / 1000.0
        return data_rows