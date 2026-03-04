from sqlalchemy import text
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Utils.Utils import ReportUtils
from Utils.Logger import RegistrarLog

class RelatorioRazaoContabil:
    def __init__(self, session):
        self.session = session

    def ObterDados(self, pagina=1, por_pagina=50, termo_busca='', tipo_visualizacao='adjusted'):
        offset = (pagina - 1) * por_pagina
        params = {'limit': por_pagina, 'offset': offset}
        filter_snippet = ""
        
        if termo_busca:
            filter_snippet = "AND (\"Conta\"::TEXT ILIKE :termo OR \"Título Conta\" ILIKE :termo OR \"Descricao\" ILIKE :termo OR \"Numero\"::TEXT ILIKE :termo OR \"origem\" ILIKE :termo)"
            params['termo'] = f"%{termo_busca}%"

        # Leitura direta, limpa e rápida da tabela Consolidada!
        sql_query = f"""
            SELECT "Id", "Fonte", "origem", "Conta", "Título Conta", "Data", "Numero", "Descricao", 
                   "Contra Partida - Credito", "Filial", "Centro de Custo", "Item", "Cod Cl. Valor", 
                   "Debito", "Credito", "Saldo", "Nome CC" as "Nome do CC", "Tipo_Operacao"
            FROM "Dre_Schema"."Tb_CTL_Razao_Consolidado" 
            WHERE "Invalido" = false {filter_snippet} 
            ORDER BY "Data" DESC, "Conta" ASC, "Numero" ASC 
            LIMIT :limit OFFSET :offset
        """
        
        sql_count = f'SELECT COUNT(*) FROM "Dre_Schema"."Tb_CTL_Razao_Consolidado" WHERE "Invalido" = false {filter_snippet}'

        try:
            total_registros = self.session.execute(text(sql_count), params).scalar() or 0
            total_paginas = (total_registros // por_pagina) + (1 if total_registros % por_pagina > 0 else 0)
            rows = self.session.execute(text(sql_query), params).fetchall()
            
            result_list = []

            for i, r in enumerate(rows, 1):
                row_dict = {
                    'id': i + offset, 'origem': r.origem, 'conta': r.Conta, 'titulo_conta': getattr(r, 'Título Conta', ''), 
                    'data': r.Data.isoformat() if r.Data else None, 'numero': r.Numero, 'descricao': r.Descricao, 
                    'centro_custo': getattr(r, 'Centro de Custo', ''), 'filial': getattr(r, 'Filial', ''), 'item': getattr(r, 'Item', ''),
                    'debito': float(r.Debito or 0), 'credito': float(r.Credito or 0), 'saldo': float(r.Saldo or 0), 'is_ajustado': False
                }
                
                # Identifica visualmente o que foi manipulado ou inserido
                if r.Tipo_Operacao and r.Tipo_Operacao != 'ORIGINAL':
                    row_dict['is_ajustado'] = True
                    if r.Tipo_Operacao == 'INCLUSAO': row_dict['origem'] = f"{r.origem} (NOVO)"
                    else: row_dict['origem'] = f"{r.origem} (EDIT)"

                result_list.append(row_dict)
                
            return {'pagina_atual': pagina, 'total_paginas': total_paginas, 'total_registros': total_registros, 'dados': result_list}
        except Exception as e:
            raise e

    def ObterResumo(self, tipo_visualizacao='adjusted'):
        try:
            sql = text("""
                SELECT COUNT(*), SUM("Debito"), SUM("Credito"), SUM("Saldo") 
                FROM "Dre_Schema"."Tb_CTL_Razao_Consolidado"
                WHERE "Invalido" = false
            """)
            base = self.session.execute(sql).fetchone()
            return {
                'total_registros': base[0] or 0, 'total_debito': float(base[1] or 0), 
                'total_credito': float(base[2] or 0), 'saldo_total': float(base[3] or 0)
            }
        except Exception as e:
            return {'total_registros': 0, 'total_debito': 0, 'total_credito': 0, 'saldo_total': 0}

    def ExportarCompleto(self, termo_busca='', tipo_visualizacao='adjusted'):
        params = {}
        filter_snippet = ""
        
        if termo_busca:
            params['termo'] = f"%{termo_busca}%"
            filter_snippet = "AND (\"Conta\"::TEXT ILIKE :termo OR \"Título Conta\" ILIKE :termo OR \"Descricao\" ILIKE :termo OR \"Numero\"::TEXT ILIKE :termo OR \"origem\" ILIKE :termo)"

        try:
            sql = text(f"""
                SELECT "origem", "Conta", "Título Conta", "Data", "Numero", "Descricao", "Contra Partida - Credito" as "Contra Partida", 
                       "Filial", "Centro de Custo", "Item", "Cod Cl. Valor", "Debito", "Credito", "Saldo", "Tipo_Operacao"
                FROM "Dre_Schema"."Tb_CTL_Razao_Consolidado" 
                WHERE "Invalido" = false {filter_snippet}
                ORDER BY "Data", "Conta"
            """)
                
            rows = self.session.execute(sql, params).fetchall()
            final_data = []

            for r in rows:
                row_dict = dict(r._mapping)
                tipo = row_dict.pop('Tipo_Operacao', 'ORIGINAL')
                
                if tipo == 'INCLUSAO': row_dict['origem'] = f"{row_dict['origem']} (NOVO)"
                elif tipo != 'ORIGINAL': row_dict['origem'] = f"{row_dict['origem']} (AJUSTE)"

                final_data.append(row_dict)
            
            return final_data
        except Exception as e:
            raise e

    def ListarCentrosCusto(self):
        try:
            sql = text("""
                SELECT DISTINCT ccc."Codigo", ccc."Nome" 
                FROM "Dre_Schema"."Tb_CTL_Razao_Consolidado" rdc 
                JOIN "Dre_Schema"."Tb_CTL_Cad_Centro_Custo" ccc ON rdc."Centro de Custo"::text = ccc."Codigo"::text
                WHERE ccc."Nome" IS NOT NULL 
                ORDER BY ccc."Nome"
            """)
            rows = self.session.execute(sql).fetchall()
            
            nome_counts = {}
            for row in rows:
                nome_counts[row.Nome] = nome_counts.get(row.Nome, 0) + 1

            lista_ccs = []
            for row in rows:
                nome_base = row.Nome
                codigo = str(row.Codigo)
                nome_exibicao = nome_base
                if nome_counts[nome_base] > 1:
                    nome_exibicao = f"{nome_base} ({codigo})"
                
                lista_ccs.append({'codigo': codigo, 'nome': nome_exibicao})
            
            return lista_ccs
        except Exception as e:
            return []