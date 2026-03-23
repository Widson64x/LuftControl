import os
import unicodedata
from functools import wraps
from flask import request, jsonify
import json
from flask_login import current_user
from Db.Connections import GetSqlServerSession 

from luftcore.extensions.flask_extension import api_error, render_no_permission, render_403
from Models.SqlServer.Permissoes import Tb_Permissao, Tb_PermissaoGrupo, Tb_PermissaoUsuario, Tb_LogAcesso
from Models.SqlServer.Usuario import Usuario as ModeloUsuario
from Utils.Logger import RegistrarLog

SISTEMA_ID = int(os.getenv("SISTEMA_ID", 2))

# --- NOVA VARIÁVEL GLOBAL DE DEBUG ---
DEBUG_PERMISSIONS = os.getenv("DEBUG_PERMISSIONS", "False").lower() == "true"

class PermissaoService:
    
    @staticmethod
    def _Normalizar(texto):
        if not texto: return ""
        return "".join(c for c in unicodedata.normalize('NFD', texto.upper().strip())
                       if unicodedata.category(c) != 'Mn')

    @staticmethod
    def VerificarPermissao(Usuario, ChavePermissao):
        # BYPASS DE DEBUG: Se o modo debug estiver on, libera geral
        if DEBUG_PERMISSIONS:
            print(f"[DEBUG MODE] 🔓 Bypass ativado para a chave: {ChavePermissao.upper()}")
            return True

        if not Usuario.is_authenticated: return False
        if getattr(Usuario, 'Grupo', '') == 'ADM_SISTEMA': return True

        Sessao = GetSqlServerSession()
        try:
            id_usuario_logado = Usuario.get_id()
            user_db = Sessao.query(ModeloUsuario).filter_by(Codigo_Usuario=id_usuario_logado).first()
            
            if not user_db: return False

            id_grupo = user_db.codigo_usuariogrupo
            chave_procurada = PermissaoService._Normalizar(ChavePermissao)

            todas_perms = Sessao.query(Tb_Permissao).filter_by(Id_Sistema=SISTEMA_ID).all()
            permissao_encontrada = next((p for p in todas_perms if PermissaoService._Normalizar(p.Chave_Permissao) == chave_procurada), None)
            
            if not permissao_encontrada: return False

            tem_acesso = False
            if id_grupo:
                tem_acesso = Sessao.query(Tb_PermissaoGrupo).filter_by(
                    Id_Permissao=permissao_encontrada.Id_Permissao,
                    Codigo_UsuarioGrupo=id_grupo
                ).count() > 0

            override = Sessao.query(Tb_PermissaoUsuario).filter_by(
                Id_Permissao=permissao_encontrada.Id_Permissao,
                Codigo_Usuario=id_usuario_logado
            ).first()

            return override.Conceder if override else tem_acesso

        except Exception as e:
            print(f"[ERRO] {str(e)}")
            return False
        finally:
            Sessao.close()

    @staticmethod
    def RegistrarLogAcesso(Usuario, Rota, Metodo, Ip, Chave, Permitido, Parametros=None, Retorno=None):
        Sessao = GetSqlServerSession()
        try:
            nome = getattr(Usuario, 'Nome_Usuario', 'Anonimo')
            if nome == 'Anonimo': nome = getattr(Usuario, 'nome', 'Anonimo')
            
            NovoLog = Tb_LogAcesso(
                Id_Sistema=SISTEMA_ID,
                Id_Usuario=Usuario.get_id() if Usuario.is_authenticated else None,
                Nome_Usuario=nome,
                Rota_Acessada=Rota,
                Metodo_Http=Metodo, 
                Ip_Origem=Ip,
                Permissao_Exigida=Chave.upper(),
                Acesso_Permitido=Permitido,
                Parametros_Requisicao=Parametros, # Passando os parâmetros
                Resposta_Acao=Retorno             # Passando o retorno
            )
            Sessao.add(NovoLog)
            Sessao.commit()
        except Exception as e: 
            print(f"[ERRO NO LOG] {str(e)}")
        finally: 
            Sessao.close()


def RequerPermissao(Chave):
    def Decorator(F):
        @wraps(F)
        def Wrapper(*args, **kwargs):
            if DEBUG_PERMISSIONS:
                return F(*args, **kwargs)

            def _is_api(): return request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            if current_user is None or not current_user.is_authenticated: return render_403("Faça login")

            Permitido = PermissaoService.VerificarPermissao(current_user, Chave)

            # --- NOVA LÓGICA PARA PEGAR O IP REAL ---
            # O X-Forwarded-For pode retornar uma lista de IPs separados por vírgula (ex: "ip_cliente, ip_proxy1").
            # O primeiro IP da lista é sempre o do cliente original.
            x_forwarded_for = request.headers.get('X-Forwarded-For')
            if x_forwarded_for:
                ip_real = x_forwarded_for.split(',')[0].strip()
            else:
                # Se não tiver o X-Forwarded-For, tenta o X-Real-IP, e em último caso o remote_addr padrão
                ip_real = request.headers.get('X-Real-IP', request.remote_addr)
            # ----------------------------------------

            params_dict = {}
            if request.args: params_dict['query'] = dict(request.args)
            if request.form: params_dict['form'] = dict(request.form)
            if request.is_json: params_dict['json'] = request.get_json(silent=True)
            
            parametros_str = json.dumps(params_dict, ensure_ascii=False) if params_dict else None

            if not Permitido:
                msg = f"Acesso negado. Requer: {Chave.upper()}"
                PermissaoService.RegistrarLogAcesso(
                    # Passa o ip_real aqui!
                    current_user, request.path, request.method, ip_real, 
                    Chave, Permitido, parametros_str, f"Erro 403: {msg}"
                )
                return api_error(msg, 403) if _is_api() else render_no_permission(msg)
            
            resposta = F(*args, **kwargs)
            
            retorno_str = None
            if hasattr(resposta, 'status_code'):
                retorno_str = f"Status HTTP: {resposta.status_code}"
            elif isinstance(resposta, tuple) and len(resposta) > 1:
                retorno_str = f"Status HTTP: {resposta[1]}"
            else:
                retorno_str = "Status HTTP: 200 (OK)"
                
            PermissaoService.RegistrarLogAcesso(
                # Passa o ip_real aqui também!
                current_user, request.path, request.method, ip_real, 
                Chave, Permitido, parametros_str, retorno_str
            )

            return resposta
            
        return Wrapper
    return Decorator