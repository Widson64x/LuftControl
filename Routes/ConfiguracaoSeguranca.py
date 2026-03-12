import os
from flask import Blueprint, render_template, request, jsonify, flash, url_for, redirect
from flask_login import login_required, current_user
from Db.Connections import GetSqlServerSession 
from Models.SqlServer.Permissoes import Tb_PLN_Permissao, Tb_PLN_PermissaoGrupo, Tb_PLN_PermissaoUsuario
from Models.SqlServer.Usuario import UsuarioGrupo, Usuario
from Services.PermissaoService import RequerPermissao, PermissaoService, DEBUG_PERMISSIONS

security_bp = Blueprint('Seguranca', __name__)
SISTEMA_ID = int(os.getenv("SISTEMA_ID", 2))

@security_bp.route('/gerenciador', methods=['GET'])
@login_required
@RequerPermissao('SEGURANCA.VISUALIZAR')
def VisualizarGerenciador():
    Sessao = GetSqlServerSession()
    try:
        Grupos = Sessao.query(UsuarioGrupo).order_by(UsuarioGrupo.Sigla_UsuarioGrupo).all()
        Usuarios = Sessao.query(Usuario.Codigo_Usuario, Usuario.Nome_Usuario, Usuario.Login_Usuario, UsuarioGrupo.Sigla_UsuarioGrupo.label('Nome_UsuarioGrupo')).outerjoin(UsuarioGrupo, Usuario.codigo_usuariogrupo == UsuarioGrupo.codigo_usuariogrupo).order_by(Usuario.Nome_Usuario).all()

        ListaPermissoes = Sessao.query(Tb_PLN_Permissao).filter_by(Id_Sistema=SISTEMA_ID).order_by(Tb_PLN_Permissao.Categoria_Permissao, Tb_PLN_Permissao.Descricao_Permissao).all()
        
        PermissoesPorCategoria = {}
        for p in ListaPermissoes:
            cat = p.Categoria_Permissao or 'Geral'
            if cat not in PermissoesPorCategoria: PermissoesPorCategoria[cat] = []
            PermissoesPorCategoria[cat].append(p)
            
        # LÓGICA AUTOMÁTICA: Responde ao que estiver no .env ou na variável global
        PodeEditar = True if DEBUG_PERMISSIONS else PermissaoService.VerificarPermissao(current_user, 'SEGURANCA.EDITAR')
        PodeCriar  = True if DEBUG_PERMISSIONS else PermissaoService.VerificarPermissao(current_user, 'SEGURANCA.CRIAR')

        return render_template('Pages/Configs/PermissionConfigs.html', Grupos=Grupos, Usuarios=Usuarios, PermissoesPorCategoria=PermissoesPorCategoria, PodeEditar=PodeEditar, PodeCriar=PodeCriar)
    finally: Sessao.close()

@security_bp.route('/api/permissoes/buscar-grupo', methods=['GET'])
@login_required
@RequerPermissao('SEGURANCA.VISUALIZAR')
def BuscarAcessosGrupo():
    IdGrupo = request.args.get('idGrupo')
    Sessao = GetSqlServerSession()
    try:
        Vinculos = Sessao.query(Tb_PLN_PermissaoGrupo).filter_by(Codigo_UsuarioGrupo=IdGrupo).all()
        return jsonify({'ids_ativos': [v.Id_Permissao for v in Vinculos]})
    finally: Sessao.close()

@security_bp.route('/api/permissoes/buscar-usuario', methods=['GET'])
@login_required
@RequerPermissao('SEGURANCA.VISUALIZAR')
def BuscarAcessosUsuario():
    IdUsuario = request.args.get('idUsuario')
    Sessao = GetSqlServerSession()
    try:
        User = Sessao.query(Usuario).filter_by(Codigo_Usuario=IdUsuario).first()
        if not User: return jsonify({'erro': 'Usuário não encontrado'}), 404
        ListaGrupo = [p.Id_Permissao for p in Sessao.query(Tb_PLN_PermissaoGrupo).filter_by(Codigo_UsuarioGrupo=User.codigo_usuariogrupo).all()]
        Overrides = Sessao.query(Tb_PLN_PermissaoUsuario).filter_by(Codigo_Usuario=IdUsuario).all()
        return jsonify({'heranca_grupo': ListaGrupo, 'usuario_permitidos': [o.Id_Permissao for o in Overrides if o.Conceder], 'usuario_bloqueados': [o.Id_Permissao for o in Overrides if not o.Conceder]})
    finally: Sessao.close()

@security_bp.route('/api/permissoes/salvar', methods=['POST'])
@login_required
@RequerPermissao('SEGURANCA.EDITAR')
def SalvarVinculo():
    Dados = request.get_json()
    IdAlvo, IdPermissao, Tipo, Acao = int(Dados.get('IdAlvo')), int(Dados.get('IdPermissao')), Dados.get('Tipo'), Dados.get('Acao')
    Sessao = GetSqlServerSession()
    try:
        if Tipo == 'Grupo':
            Vinculo = Sessao.query(Tb_PLN_PermissaoGrupo).filter_by(Codigo_UsuarioGrupo=IdAlvo, Id_Permissao=IdPermissao).first()
            if Acao == 'Adicionar' and not Vinculo: Sessao.add(Tb_PLN_PermissaoGrupo(Codigo_UsuarioGrupo=IdAlvo, Id_Permissao=IdPermissao))
            elif Acao == 'Remover' and Vinculo: Sessao.delete(Vinculo)
        else:
            Vinculo = Sessao.query(Tb_PLN_PermissaoUsuario).filter_by(Codigo_Usuario=IdAlvo, Id_Permissao=IdPermissao).first()
            if Acao == 'Resetar': 
                if Vinculo: Sessao.delete(Vinculo)
            else:
                Estado = True if Acao == 'Permitir' else False
                if not Vinculo: Sessao.add(Tb_PLN_PermissaoUsuario(Codigo_Usuario=IdAlvo, Id_Permissao=IdPermissao, Conceder=Estado))
                else: Vinculo.Conceder = Estado
        Sessao.commit()
        return jsonify({'sucesso': True})
    except Exception as e:
        Sessao.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)})
    finally: Sessao.close()

@security_bp.route('/api/permissoes/criar', methods=['POST'])
@login_required
@RequerPermissao('SEGURANCA.CRIAR')
def CriarNovaPermissao():
    Dados = request.form
    Modulo = Dados.get('modulo').upper().strip().replace(' ', '_')
    Acao = Dados.get('acao').upper().strip()
    Excecao = Dados.get('excecao').upper().strip().replace(' ', '_') if Dados.get('excecao') else None
    
    # CHAVE LIMPA: SEGURANCA.VISUALIZAR (O Id_Sistema já está na outra coluna)
    ChaveFinal = f"{Modulo}.{Excecao}.{Acao}" if Excecao else f"{Modulo}.{Acao}"
    
    Sessao = GetSqlServerSession()
    try:
        Existe = Sessao.query(Tb_PLN_Permissao).filter_by(Chave_Permissao=ChaveFinal, Id_Sistema=SISTEMA_ID).first()
        if Existe:
            flash(f'A chave "{ChaveFinal}" já existe.', 'warning')
        else:
            Sessao.add(Tb_PLN_Permissao(
                Id_Sistema=SISTEMA_ID,
                Chave_Permissao=ChaveFinal,
                Descricao_Permissao=Dados.get('descricao'),
                Categoria_Permissao=Modulo
            ))
            Sessao.commit()
            flash('Permissão criada com sucesso!', 'success')
    except Exception as e:
        Sessao.rollback()
        flash(f"Erro: {str(e)}", 'danger')
    finally:
        Sessao.close()
    return redirect(url_for('Seguranca.VisualizarGerenciador'))