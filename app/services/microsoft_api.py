import requests
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
import time

logger = logging.getLogger(__name__)

class MicrosoftPlannerAPI:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        # Configurações de retry
        self.max_retries = 3
        self.retry_delay = 2  # segundos
    
    def make_request(self, endpoint: str, params: Dict = None, method: str = 'GET', data: Dict = None, retry_count: int = 0):
        """Faz requisição para Microsoft Graph API com retry automático"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, json=data, timeout=30)
            elif method == 'PATCH':
                response = requests.patch(url, headers=self.headers, json=data, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=self.headers, timeout=30)
            else:
                raise ValueError(f"Método HTTP não suportado: {method}")
            
            response.raise_for_status()
            
            if response.status_code == 204:  # No Content
                return True
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            # Verificar se é um erro que vale a pena tentar novamente
            should_retry = False
            
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                
                # Erros temporários que vale a pena tentar novamente
                if status_code in [429, 502, 503, 504]:  # Too Many Requests, Bad Gateway, Service Unavailable, Gateway Timeout
                    should_retry = True
                    error_name = {
                        429: "Rate Limit (429)",
                        502: "Bad Gateway (502)",
                        503: "Service Unavailable (503)",
                        504: "Gateway Timeout (504)"
                    }.get(status_code, f"Erro {status_code}")
                    
                    logger.warning(f"{error_name} na requisição para {url}")
                elif status_code == 404:
                    # NOVO: 404 é esperado para recursos que não existem (não é erro grave)
                    logger.debug(f"Recurso não encontrado (404): {url}")
                else:
                    logger.error(f"Erro na requisição para {url}: {str(e)}")
                
                # Log da resposta de erro apenas se não for 502 ou 404 (evita poluir logs)
                if status_code not in [502, 404]:
                    logger.error(f"Resposta de erro: {e.response.text[:500]}")  # Limitar tamanho do log
            else:
                # Erros de timeout também podem ser tentados novamente
                if isinstance(e, requests.exceptions.Timeout):
                    should_retry = True
                    logger.warning(f"Timeout na requisição para {url}")
                else:
                    logger.error(f"Erro na requisição para {url}: {str(e)}")
            
            # Tentar novamente se apropriado
            if should_retry and retry_count < self.max_retries:
                retry_count += 1
                wait_time = self.retry_delay * retry_count  # Backoff exponencial
                logger.info(f"Tentando novamente em {wait_time}s... (tentativa {retry_count}/{self.max_retries})")
                time.sleep(wait_time)
                return self.make_request(endpoint, params, method, data, retry_count)
            
            return None
    
    def get_me(self):
        """Obtém informações do usuário atual"""
        return self.make_request('/me')
    
    def get_groups(self, limit: int = 100):
        """Lista grupos do usuário"""
        params = {
            '$top': limit,
            '$select': 'id,displayName,mail,description,groupTypes,visibility,createdDateTime'
        }
        return self.make_request('/me/transitiveMemberOf/microsoft.graph.group', params)
    
    def get_planners(self, group_id: str):
        """Lista planners de um grupo"""
        return self.make_request(f'/groups/{group_id}/planner/plans')
    
    def get_planner_details(self, plan_id: str):
        """Obtém detalhes de um planner"""
        return self.make_request(f'/planner/plans/{plan_id}')
    
    def get_planner_tasks(self, plan_id: str, limit: int = 1000):
        """Lista tarefas de um planner"""
        params = {'$top': limit}
        return self.make_request(f'/planner/plans/{plan_id}/tasks', params)
    
    def get_task_details(self, task_id: str):
        """Obtém detalhes de uma tarefa"""
        return self.make_request(f'/planner/tasks/{task_id}')
    
    def get_buckets(self, plan_id: str):
        """Lista buckets de um planner"""
        return self.make_request(f'/planner/plans/{plan_id}/buckets')
    
    def create_task(self, plan_id: str, task_data: Dict):
        """Cria uma nova tarefa"""
        return self.make_request(
            f'/planner/plans/{plan_id}/tasks',
            method='POST',
            data=task_data
        )
    
    def update_task(self, task_id: str, task_data: Dict):
        """Atualiza uma tarefa existente"""
        return self.make_request(
            f'/planner/tasks/{task_id}',
            method='PATCH',
            data=task_data
        )
    
    def delete_task(self, task_id: str):
        """Exclui uma tarefa"""
        return self.make_request(f'/planner/tasks/{task_id}', method='DELETE')
    
    def get_task_assigned_to(self, task_id: str):
        """Obtém responsáveis pela tarefa"""
        return self.make_request(f'/planner/tasks/{task_id}/assignedToTaskBoardFormat')
    
    def get_task_progress(self, task_id: str):
        """Obtém progresso da tarefa"""
        return self.make_request(f'/planner/tasks/{task_id}/progressTaskBoardFormat')
    
    def get_user_details(self, user_id: str):
        """Obtém detalhes de um usuário"""
        return self.make_request(f'/users/{user_id}')
    
    def search_users(self, query: str, limit: int = 20):
        """Busca usuários no Azure AD"""
        params = {
            '$search': f'"displayName:{query}" OR "mail:{query}"',
            '$select': 'id,displayName,mail,userPrincipalName,jobTitle,department',
            '$top': limit
        }
        return self.make_request('/users', params)