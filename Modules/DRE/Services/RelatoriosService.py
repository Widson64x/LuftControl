from sqlalchemy.orm import sessionmaker
import pandas as pd
import io

# --- Imports de Banco de Dados ---
from Db.Connections import GetPostgresEngine

# --- Imports dos Relatórios (Novos Nomes) ---
from Modules.DRE.Reports.RazaoContabil import RazaoContabil
from Modules.DRE.Reports.DreGerencial import DreGerencial
from Modules.DRE.Reports.DreConsolidado import DreConsolidado

# --- Import do Logger ---
from Utils.Logger import RegistrarLog

class RelatoriosService:
    """
    Serviço centralizador para geração de relatórios.
    Gerencia o ciclo de vida da sessão do banco e executa as lógicas de negócio.
    """
    
    def __init__(self):
        pass

    def _ObterSessao(self):
        """Cria e retorna uma sessão do PostgreSQL."""
        engine = GetPostgresEngine()
        return sessionmaker(bind=engine)()

    # ============================================================
    # MÉTODOS DO RAZÃO CONTÁBIL
    # ============================================================

    def ObterDadosRazao(self, pagina, por_pagina, termo_busca, tipo_visualizacao):
        """Wrapper para ObterDados do RazaoContabil."""
        session = self._ObterSessao()
        try:
            relatorio = RazaoContabil(session)
            return relatorio.ObterDados(pagina, por_pagina, termo_busca, tipo_visualizacao)
        finally:
            session.close()

    def ObterResumoRazao(self, tipo_visualizacao):
        """Wrapper para ObterResumo do RazaoContabil."""
        session = self._ObterSessao()
        try:
            relatorio = RazaoContabil(session)
            return relatorio.ObterResumo(tipo_visualizacao)
        finally:
            session.close()

    def ListarCentrosCusto(self):
        """Wrapper para ListarCentrosCusto."""
        session = self._ObterSessao()
        try:
            relatorio = RazaoContabil(session)
            return relatorio.ListarCentrosCusto()
        finally:
            session.close()

    def GerarExcelRazao(self, termo_busca, tipo_visualizacao):
        """
        Serviço que gera o binário do Excel para download.
        Reutiliza a lógica de ExportarCompleto do relatório.
        """
        session = self._ObterSessao()
        try:
            relatorio = RazaoContabil(session)
            data_rows = relatorio.ExportarCompleto(termo_busca, tipo_visualizacao)
            
            if not data_rows:
                return None

            # Conversão para DataFrame (Lógica trazida da Rota para o Service)
            df = pd.DataFrame(data_rows)
            if 'Data' in df.columns:
                df['Data'] = pd.to_datetime(df['Data']).dt.strftime('%d/%m/%Y')

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Razão Full')
                worksheet = writer.sheets['Razão Full']
                for idx, col in enumerate(df.columns):
                    # Ajuste automático de largura de coluna
                    max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                    worksheet.set_column(idx, idx, min(max_len, 60))
            
            output.seek(0)
            return output
        except Exception as e:
            RegistrarLog("Erro no serviço de geração de Excel", "ERROR", e)
            raise e
        finally:
            session.close()

    # ============================================================
    # MÉTODOS DO DRE GERENCIAL
    # ============================================================

    def GerarDreRentabilidade(self, origem, filtro_cc, modo_escala, ano=None):
        """
        Serviço para calcular e formatar o DRE Gerencial.
        Executa: Processamento -> Cálculo Fórmulas -> Formatação Escala.
        """
        session = self._ObterSessao()
        try:
            relatorio = DreGerencial(session)
            
            # 1. Busca Dados Base e Aplica Hierarquia
            # [ATUALIZADO] Repassando o ano para o motor
            dados = relatorio.ProcessarRelatorio(
                filtro_origem=origem, 
                agrupar_por_cc=False, 
                filtro_cc=filtro_cc,
                ano=ano
            )
            
            # 2. Executa Fórmulas (Margens, EBITDA, etc)
            dados_calculados = relatorio.CalcularNosVirtuais(dados)
            
            # 3. Formatação
            if modo_escala == 'dre':
                return relatorio.AplicarMilhares(dados_calculados)
                
            return dados_calculados
        finally:
            session.close()

    def GerarDreConsolidado(self, modo_escala, ano=None):
        """
        Serviço para calcular o DRE com colunas por unidade de negócio.
        """
        session = self._ObterSessao()
        try:
            relatorio = DreConsolidado(session)
            
            # 1. Busca e mapeia nas colunas novas
            dados = relatorio.ProcessarRelatorio(ano=ano)
            
            # 2. Executa Fórmulas
            dados_calculados = relatorio.CalcularNosVirtuais(dados)
            
            # 3. Formatação
            if modo_escala == 'dre':
                return relatorio.AplicarMilhares(dados_calculados)
                
            return dados_calculados
        finally:
            session.close()

    def GerarDreOperacao(self, modo_escala='dre', ano=None):
        """
        Serviço para calcular o DRE com colunas por Operação.
        """
        session = self._ObterSessao() # <- AQUI ESTÁ A CORREÇÃO
        try:
            from Modules.DRE.Reports.DreOperacao import DreOperacao
            relatorio = DreOperacao(session)
            
            # 1. Busca e mapeia nas colunas novas
            dados = relatorio.ProcessarRelatorio(ano=ano)
            
            # 2. Executa Fórmulas
            dados_calculados = relatorio.CalcularNosVirtuais(dados)
            
            # 3. Formatação
            if modo_escala == 'dre':
                return relatorio.AplicarMilhares(dados_calculados)
                
            return dados_calculados
        finally:
            session.close()

    def DepurarOrdenamentoDre(self):
        """Wrapper para DepurarEstruturaEOrdem."""
        session = self._ObterSessao()
        try:
            relatorio = DreGerencial(session)
            return relatorio.DepurarEstruturaEOrdem()
        finally:
            session.close()