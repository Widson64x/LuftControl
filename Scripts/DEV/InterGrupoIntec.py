# No topo do ImportacaoDadosService.py, adicione o import:
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from Utils.Logger import RegistrarLog
from Utils.ExcelUtils import ler_qvd_para_dataframe
from Settings import BaseConfig

"""
    Código para realizar o fluxo de Intergrupo da INTEC.
    Passo 1: Carregar o QVD de Valor Financeiro.
    Passo 2: (a ser implementado) Processar os dados conforme a lógica de negócio. Foi feito na classe AjustesManuaisService.
"""
class ImportacaoDadosService:
    # ... outros métodos e inicializadores ...
    # Dentro da classe ImportacaoDadosService:
    def ProcessarIntergrupoIntec(self):
        """
        Método específico para tratar o Intergrupo da INTEC.
        Passo 1: Carregar o QVD de Valor Financeiro.
        """
        caminho_qvd = os.path.join(BaseConfig().DataQVDPath(), "ValorFinanceiro.qvd")
        try:
            df_valor_financeiro = ler_qvd_para_dataframe(caminho_qvd)
            
            # O DataFrame está pronto para uso nos próximos passos da lógica
            return df_valor_financeiro
            
        except Exception as e:
            RegistrarLog("Erro no fluxo de Intergrupo INTEC", "ERROR", e)
            raise e
        
def main():
    service = ImportacaoDadosService()
    df = service.ProcessarIntergrupoIntec()
    
    if df is not None:
        print("✅ QVD carregado com sucesso!")
        print(f"Total de linhas: {len(df)}")
        print("\nPrimeiras 5 linhas:")
        print(df.head())
    else:
        print("❌ Falha ao carregar o DataFrame.")

if __name__ == "__main__":
    main()
    
    
main()