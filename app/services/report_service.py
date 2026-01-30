import pandas as pd
import plotly.graph_objs as go
import plotly.express as px
from datetime import datetime, timedelta
from io import BytesIO
import json
import logging
from sqlalchemy import func, desc, and_, or_
from app.models import db, Task, Planner, Group, User, TaskStatus, TaskPriority

logger = logging.getLogger(__name__)

class ReportService:
    def __init__(self, current_user):
        self.current_user = current_user
    
    def generate_task_report(self, filters):
        """Gera relatório de tarefas"""
        try:
            query = Task.query.join(Planner).join(Group)
            
            # Aplicar filtros
            query = self._apply_filters(query, filters)
            
            tasks = query.all()
            
            # Criar DataFrame
            data = []
            for task in tasks:
                assignments = task.get_assignments()
                assignee_names = []
                assignee_emails = []
                
                for user_id, assignment in assignments.items():
                    assignee_names.append(assignment.get('userDisplayName', ''))
                    assignee_email = assignment.get('userEmail', '')
                    if assignee_email:
                        assignee_emails.append(assignee_email)
                
                data.append({
                    'ID': task.id[:8],
                    'Título': task.title,
                    'Descrição': task.description[:100] if task.description else '',
                    'Status': task.status.value if task.status else '',
                    'Prioridade': task.priority.value if task.priority else 0,
                    'Progresso': f"{task.percent_complete}%",
                    'Data Início': task.start_date.strftime('%d/%m/%Y') if task.start_date else '',
                    'Data Vencimento': task.due_date.strftime('%d/%m/%Y') if task.due_date else '',
                    'Data Conclusão': task.completed_date.strftime('%d/%m/%Y') if task.completed_date else '',
                    'Responsáveis': ', '.join(assignee_names),
                    'Emails': ', '.join(assignee_emails),
                    'Planner': task.planner.title if task.planner else '',
                    'Grupo': task.planner.group.name if task.planner and task.planner.group else '',
                    'Bucket': task.bucket.name if task.bucket else '',
                    'Atrasada': 'Sim' if task.is_overdue else 'Não',
                    'Bloqueada': 'Sim' if task.is_blocked else 'Não',
                    'Dias Restantes': task.days_until_due if task.days_until_due else '',
                    'Comentários': task.comments_count,
                    'Checklists': f"{task.checklists_completed}/{task.checklists_total}",
                    'Esforço': task.effort if task.effort else '',
                    'Valor': task.business_value if task.business_value else '',
                    'Criada em': task.created_date.strftime('%d/%m/%Y %H:%M') if task.created_date else ''
                })
            
            df = pd.DataFrame(data)
            
            # Gerar sumário
            summary = self._generate_summary(tasks)
            
            return {
                'dataframe': df,
                'summary': summary,
                'total_tasks': len(tasks)
            }
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório de tarefas: {str(e)}")
            raise
    
    def generate_performance_report(self, start_date, end_date):
        """Gera relatório de performance"""
        try:
            # Estatísticas por usuário
            users_stats = []
            users = User.query.filter_by(is_active=True).all()
            
            for user in users:
                # Tarefas atribuídas
                tasks_query = Task.query.filter(
                    Task.assignments_json.like(f'%"userId": "{user.azure_id}"%')
                )
                
                if start_date:
                    tasks_query = tasks_query.filter(Task.created_date >= start_date)
                if end_date:
                    tasks_query = tasks_query.filter(Task.created_date <= end_date)
                
                tasks = tasks_query.all()
                
                if tasks:
                    completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
                    overdue = sum(1 for t in tasks if t.is_overdue)
                    completion_rate = (completed / len(tasks)) * 100 if tasks else 0
                    
                    users_stats.append({
                        'Usuário': user.display_name,
                        'Email': user.email,
                        'Total Tarefas': len(tasks),
                        'Concluídas': completed,
                        'Atrasadas': overdue,
                        'Taxa Conclusão': f"{completion_rate:.1f}%",
                        'Departamento': user.department or ''
                    })
            
            # Estatísticas por planner
            planners_stats = []
            planners = Planner.query.all()
            
            for planner in planners:
                tasks = planner.tasks
                if tasks:
                    completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
                    overdue = sum(1 for t in tasks if t.is_overdue)
                    completion_rate = (completed / len(tasks)) * 100 if tasks else 0
                    
                    planners_stats.append({
                        'Planner': planner.title,
                        'Grupo': planner.group.name if planner.group else '',
                        'Total Tarefas': len(tasks),
                        'Concluídas': completed,
                        'Atrasadas': overdue,
                        'Em Progresso': planner.in_progress_tasks,
                        'Não Iniciadas': planner.not_started_tasks,
                        'Taxa Conclusão': f"{completion_rate:.1f}%"
                    })
            
            # Tendências ao longo do tempo
            trends = self._generate_trends(start_date, end_date)
            
            return {
                'users_stats': pd.DataFrame(users_stats),
                'planners_stats': pd.DataFrame(planners_stats),
                'trends': trends
            }
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório de performance: {str(e)}")
            raise
    
    def generate_custom_report(self, report_config):
        """Gera relatório customizado"""
        try:
            report_type = report_config.get('type')
            
            if report_type == 'task_distribution':
                return self._generate_task_distribution_report(report_config)
            elif report_type == 'timeline':
                return self._generate_timeline_report(report_config)
            elif report_type == 'burndown':
                return self._generate_burndown_report(report_config)
            elif report_type == 'workload':
                return self._generate_workload_report(report_config)
            else:
                raise ValueError(f"Tipo de relatório não suportado: {report_type}")
                
        except Exception as e:
            logger.error(f"Erro ao gerar relatório customizado: {str(e)}")
            raise
    
    def export_to_excel(self, report_data, filename):
        """Exporta relatório para Excel"""
        try:
            output = BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Adicionar múltiplas abas se necessário
                if 'dataframe' in report_data:
                    report_data['dataframe'].to_excel(writer, sheet_name='Tarefas', index=False)
                
                if 'summary' in report_data:
                    summary_df = pd.DataFrame([report_data['summary']])
                    summary_df.to_excel(writer, sheet_name='Sumário', index=False)
                
                if 'users_stats' in report_data and not report_data['users_stats'].empty:
                    report_data['users_stats'].to_excel(writer, sheet_name='Performance Usuários', index=False)
                
                if 'planners_stats' in report_data and not report_data['planners_stats'].empty:
                    report_data['planners_stats'].to_excel(writer, sheet_name='Performance Planners', index=False)
                
                # Adicionar gráficos se disponíveis
                if 'charts' in report_data:
                    self._add_charts_to_excel(writer, report_data['charts'])
            
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Erro ao exportar para Excel: {str(e)}")
            raise
    
    def export_to_pdf(self, report_data, filename):
        """Exporta relatório para PDF"""
        # Implementação usando ReportLab ou WeasyPrint
        pass
    
    def _apply_filters(self, query, filters):
        """Aplica filtros à query"""
        if filters.get('status'):
            query = query.filter(Task.status == filters['status'])
        
        if filters.get('priority'):
            query = query.filter(Task.priority == filters['priority'])
        
        if filters.get('planner_id'):
            query = query.filter(Task.planner_id == filters['planner_id'])
        
        if filters.get('group_id'):
            query = query.join(Planner).filter(Planner.group_id == filters['group_id'])
        
        if filters.get('assigned_to'):
            query = query.filter(Task.assignments_json.like(f'%"userId": "{filters["assigned_to"]}"%'))
        
        if filters.get('start_date_from'):
            query = query.filter(Task.start_date >= filters['start_date_from'])
        
        if filters.get('start_date_to'):
            query = query.filter(Task.start_date <= filters['start_date_to'])
        
        if filters.get('due_date_from'):
            query = query.filter(Task.due_date >= filters['due_date_from'])
        
        if filters.get('due_date_to'):
            query = query.filter(Task.due_date <= filters['due_date_to'])
        
        if filters.get('overdue_only'):
            query = query.filter(Task.is_overdue == True)
        
        if filters.get('blocked_only'):
            query = query.filter(Task.is_blocked == True)
        
        if filters.get('search'):
            search = f"%{filters['search']}%"
            query = query.filter(
                or_(
                    Task.title.ilike(search),
                    Task.description.ilike(search)
                )
            )
        
        return query
    
    def _generate_summary(self, tasks):
        """Gera sumário das tarefas"""
        if not tasks:
            return {}
        
        total = len(tasks)
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        in_progress = sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS)
        not_started = sum(1 for t in tasks if t.status == TaskStatus.NOT_STARTED)
        overdue = sum(1 for t in tasks if t.is_overdue)
        blocked = sum(1 for t in tasks if t.is_blocked)
        
        # Calcular médias
        avg_completion = sum(t.percent_complete for t in tasks) / total if total > 0 else 0
        avg_days_until_due = sum(t.days_until_due for t in tasks if t.days_until_due is not None) / total if total > 0 else 0
        
        return {
            'Total Tarefas': total,
            'Concluídas': completed,
            'Em Progresso': in_progress,
            'Não Iniciadas': not_started,
            'Atrasadas': overdue,
            'Bloqueadas': blocked,
            'Taxa Conclusão': f"{(completed/total)*100:.1f}%" if total > 0 else "0%",
            'Progresso Médio': f"{avg_completion:.1f}%",
            'Dias Médios até Vencimento': f"{avg_days_until_due:.1f}",
            'Prioridade Alta': sum(1 for t in tasks if t.priority == TaskPriority.HIGH),
            'Prioridade Urgente': sum(1 for t in tasks if t.priority == TaskPriority.URGENT)
        }
    
    def _generate_task_distribution_report(self, config):
        """Gera relatório de distribuição de tarefas"""
        # Implementação específica
        pass
    
    def _generate_timeline_report(self, config):
        """Gera relatório de timeline"""
        # Implementação específica
        pass
    
    def _generate_burndown_report(self, config):
        """Gera relatório de burndown"""
        # Implementação específica
        pass
    
    def _generate_workload_report(self, config):
        """Gera relatório de workload"""
        # Implementação específica
        pass
    
    def _generate_trends(self, start_date, end_date):
        """Gera tendências ao longo do tempo"""
        # Implementação específica
        pass
    
    def _add_charts_to_excel(self, writer, charts):
        """Adiciona gráficos ao Excel"""
        # Implementação usando openpyxl para adicionar gráficos
        pass