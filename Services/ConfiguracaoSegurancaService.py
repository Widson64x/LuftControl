from sqlalchemy.orm import sessionmaker
from Db.Connections import GetPostgresEngine
from Models.POSTGRESS.Seguranca import SecUserExtension, SecRole, SecPermission

class ConfiguracaoSegurancaService:
    """
    Serviço responsável pela lógica de negócios da configuração de segurança.
    Gerencia usuários, papéis (roles) e permissões.
    """

    @staticmethod
    def _ObterSessao():
        """Cria e retorna uma sessão isolada do Postgres."""
        engine = GetPostgresEngine()
        return sessionmaker(bind=engine)()

    @staticmethod
    def ObterGrafoDeSeguranca():
        """
        Retorna a estrutura de nós e arestas para desenhar o grafo visual de segurança.
        Processa papéis, usuários e permissões.
        """
        session = ConfiguracaoSegurancaService._ObterSessao()
        try:
            nodes = []
            edges = []

            # 1. Processa Papéis (Roles)
            roles = session.query(SecRole).all()
            for r in roles:
                role_node_id = f"role_{r.Id}"
                nodes.append({
                    "id": role_node_id,
                    "label": r.Nome,
                    "group": "role",
                    "title": f"Grupo: {r.Descricao}",
                    "value": 25
                })

                # Conecta Grupo -> Permissão
                for perm in r.permissions:
                    perm_id = f"perm_{perm.Id}"
                    ConfiguracaoSegurancaService._AdicionarNoPermissao(nodes, perm)
                    edges.append({
                        "from": role_node_id,
                        "to": perm_id,
                        "arrows": "to",
                        "color": {"color": "#6C5CE7", "opacity": 0.4}
                    })

            # 2. Processa Usuários
            users = session.query(SecUserExtension).all()
            for u in users:
                user_node_id = f"user_{u.Id}"
                nodes.append({
                    "id": user_node_id,
                    "label": u.Login_Usuario,
                    "group": "user",
                    "value": 15
                })

                # Conecta Usuário -> Grupo
                if u.RoleId:
                    edges.append({
                        "from": user_node_id,
                        "to": f"role_{u.RoleId}",
                        "length": 100,
                        "color": {"color": "#00B894"},
                        "width": 2
                    })
                else:
                    ConfiguracaoSegurancaService._AdicionarNoSemAcesso(nodes)
                    edges.append({
                        "from": user_node_id,
                        "to": "no_access",
                        "dashes": [5, 5],
                        "color": "#ff7675"
                    })

                # 3. Conecta Usuário -> Permissões Diretas (Exceções)
                for direct_perm in u.direct_permissions:
                    perm_id = f"perm_{direct_perm.Id}"
                    ConfiguracaoSegurancaService._AdicionarNoPermissao(nodes, direct_perm)
                    edges.append({
                        "from": user_node_id,
                        "to": perm_id,
                        "arrows": "to",
                        "color": {"color": "#fdcb6e"},
                        "dashes": [2, 2]
                    })

            return {"nodes": nodes, "edges": edges}

        except Exception as e:
            raise e
        finally:
            session.close()

    @staticmethod
    def _AdicionarNoPermissao(lista_nos, obj_permissao):
        """Auxiliar: Adiciona um nó de permissão à lista se não existir."""
        pid = f"perm_{obj_permissao.Id}"
        if not any(n['id'] == pid for n in lista_nos):
            lista_nos.append({
                "id": pid,
                "label": obj_permissao.Slug,
                "group": "permission",
                "title": obj_permissao.Descricao,
                "value": 8
            })

    @staticmethod
    def _AdicionarNoSemAcesso(lista_nos):
        """Auxiliar: Adiciona o nó de alerta 'Sem Grupo'."""
        if not any(n['id'] == 'no_access' for n in lista_nos):
            lista_nos.append({
                "id": "no_access",
                "label": "Sem Grupo",
                "group": "warning",
                "shape": "triangle",
                "value": 20
            })

    @staticmethod
    def ObterUsuariosAtivos():
        """Lista usuários cadastrados na tabela de extensão de segurança."""
        session = ConfiguracaoSegurancaService._ObterSessao()
        try:
            users = session.query(SecUserExtension).all()
            resultado = []
            for u in users:
                perms_diretas = [p.Id for p in u.direct_permissions]
                resultado.append({
                    "id": u.Id,
                    "login": u.Login_Usuario,
                    "role_id": u.RoleId,
                    "role_name": u.role.Nome if u.role else "Sem Grupo",
                    "direct_permissions": perms_diretas
                })
            return resultado
        finally:
            session.close()

    @staticmethod
    def AtualizarPapelUsuario(login, role_id):
        """Define ou altera o Papel (Role) de um usuário."""
        session = ConfiguracaoSegurancaService._ObterSessao()
        try:
            user_ext = session.query(SecUserExtension).filter_by(Login_Usuario=login).first()

            if not user_ext:
                user_ext = SecUserExtension(Login_Usuario=login)
                session.add(user_ext)

            user_ext.RoleId = int(role_id) if role_id else None
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def ObterPapeisEPermissoes():
        """Retorna todos os Grupos e todas as Permissões para o frontend."""
        session = ConfiguracaoSegurancaService._ObterSessao()
        try:
            all_perms = session.query(SecPermission).all()
            perms_list = [{"id": p.Id, "slug": p.Slug, "desc": p.Descricao} for p in all_perms]

            roles = session.query(SecRole).all()
            roles_data = []
            for r in roles:
                roles_data.append({
                    "id": r.Id,
                    "nome": r.Nome,
                    "descricao": r.Descricao,
                    "permissions": [p.Id for p in r.permissions]
                })

            return {"roles": roles_data, "all_permissions": perms_list}
        finally:
            session.close()

    @staticmethod
    def SalvarPapel(role_id, nome, descricao, ids_permissoes):
        """Cria ou edita um Grupo (Role) e suas permissões."""
        session = ConfiguracaoSegurancaService._ObterSessao()
        try:
            if role_id:
                role = session.query(SecRole).get(role_id)
            else:
                role = SecRole()
                session.add(role)

            role.Nome = nome
            role.Descricao = descricao

            # Atualiza permissões
            role.permissions = []
            if ids_permissoes:
                perms = session.query(SecPermission).filter(SecPermission.Id.in_(ids_permissoes)).all()
                role.permissions = perms

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def SalvarPermissao(slug, descricao):
        """Cria uma nova Permissão no sistema."""
        session = ConfiguracaoSegurancaService._ObterSessao()
        try:
            exists = session.query(SecPermission).filter_by(Slug=slug).first()
            if exists:
                raise ValueError("Ops! Já existe uma permissão com este Slug.")

            new_perm = SecPermission(Slug=slug, Descricao=descricao)
            session.add(new_perm)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def ExcluirPapel(role_id):
        """Exclui um Grupo e remove a associação dos usuários."""
        session = ConfiguracaoSegurancaService._ObterSessao()
        try:
            role = session.query(SecRole).get(role_id)
            if not role:
                raise ValueError("Grupo não encontrado.")

            users = session.query(SecUserExtension).filter_by(RoleId=role_id).all()
            for u in users:
                u.RoleId = None

            session.delete(role)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def ExcluirPermissao(perm_id):
        """Exclui uma Permissão do sistema."""
        session = ConfiguracaoSegurancaService._ObterSessao()
        try:
            perm = session.query(SecPermission).get(perm_id)
            if not perm:
                raise ValueError("Permissão não encontrada.")

            session.delete(perm)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def AlternarPermissaoDireta(login, perm_id, acao):
        """Adiciona ou remove permissão direta de um usuário."""
        session = ConfiguracaoSegurancaService._ObterSessao()
        try:
            user = session.query(SecUserExtension).filter_by(Login_Usuario=login).first()
            perm = session.query(SecPermission).get(perm_id)

            if not user or not perm:
                raise ValueError("Usuário ou Permissão não encontrados.")

            if acao == 'add':
                if perm not in user.direct_permissions:
                    user.direct_permissions.append(perm)
            elif acao == 'remove':
                if perm in user.direct_permissions:
                    user.direct_permissions.remove(perm)

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()