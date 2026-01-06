import sys, os
from sqlalchemy import text

# Ajusta o path para importar módulos da raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Db.Connections import GetPostgresEngine
from sqlalchemy.orm import sessionmaker
from Models.POSTGRESS.Seguranca import SecPermission, SecRole, SecUserExtension

def grant_admin():
    # SEU USUÁRIO DE LOGIN (Conforme visto no log)
    MEU_LOGIN = "widson.araujo"  # <--- CONFIRME SE É ESSE O LOGIN EXATO
    
    engine = GetPostgresEngine()
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print("--- INICIANDO CONCESSÃO DE ACESSO ---")

    try:
        # 1. Garantir que as Permissões Essenciais existem
        perms_necessarias = [
            {"slug": "security.view", "desc": "Ver Gerenciador de Segurança"},
            {"slug": "security.manage", "desc": "Gerenciar Usuários e Permissões"},
            {"slug": "dre.view", "desc": "Visualizar DRE"},
            {"slug": "config.dre", "desc": "Configurar DRE"}
        ]

        lista_perms_db = []
        for p_data in perms_necessarias:
            perm = session.query(SecPermission).filter_by(Slug=p_data['slug']).first()
            if not perm:
                perm = SecPermission(Slug=p_data['slug'], Descricao=p_data['desc'])
                session.add(perm)
                print(f"[+] Permissão criada: {p_data['slug']}")
            lista_perms_db.append(perm)
        
        session.flush() # Garante IDs

        # 2. Garantir que o Papel 'Administrador' existe e tem TODAS as permissões
        admin_role = session.query(SecRole).filter_by(Nome="Administrador").first()
        if not admin_role:
            admin_role = SecRole(Nome="Administrador", Descricao="Acesso total ao sistema")
            session.add(admin_role)
            print("[+] Grupo 'Administrador' criado.")
        
        # Atualiza as permissões do grupo Admin (sobrescreve para garantir que tenha tudo)
        admin_role.permissions = session.query(SecPermission).all()
        print(f"[.] Grupo Admin agora tem {len(admin_role.permissions)} permissões.")

        # 3. Vincular SEU USUÁRIO ao Admin
        meu_usuario = session.query(SecUserExtension).filter_by(Login_Usuario=MEU_LOGIN).first()
        
        if not meu_usuario:
            # Se não existir, cria
            meu_usuario = SecUserExtension(Login_Usuario=MEU_LOGIN)
            session.add(meu_usuario)
            print(f"[+] Usuário '{MEU_LOGIN}' criado no Postgres.")
        
        # Define o papel
        meu_usuario.role = admin_role
        print(f"[!] Usuário '{MEU_LOGIN}' promovido a Administrador.")

        session.commit()
        print("\n✅ SUCESSO! Tente acessar a página /SecurityConfig/Manager agora.")

    except Exception as e:
        session.rollback()
        print(f"\n❌ ERRO: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    grant_admin()