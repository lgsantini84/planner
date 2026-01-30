# app/utils/task_filters.py
from flask import request, session
from sqlalchemy import and_, or_, func
from datetime import datetime, timedelta
import json
from app.models import Task, Planner, TaskStatus, TaskPriority

class TaskFilter:
    """Sistema avançado de filtros para tarefas"""
    
    @staticmethod
    def apply_filters(query, filter_params):
        """Aplica múltiplos filtros à query"""
        
        # Filtro por status
        if filter_params.get('status'):
            status_list = filter_params['status'].split(',')
            query = query.filter(Task.status.in_(status_list))
        
        # Filtro por prioridade
        if filter_params.get('priority'):
            try:
                priority_list = [int(p) for p in filter_params['priority'].split(',')]
                query = query.filter(Task.priority.in_(priority_list))
            except ValueError:
                pass
        
        # Filtro por planner
        if filter_params.get('planner_id'):
            query = query.filter(Task.planner_id == filter_params['planner_id'])
        
        # Filtro por grupo - CORREÇÃO AQUI: evitar JOIN duplicado
        if filter_params.get('group_id'):
            # Primeiro verificar se já tem join com Planner
            # Se não tiver, fazer o join
            query = query.join(Planner, Planner.id == Task.planner_id)
            query = query.filter(Planner.group_id == filter_params['group_id'])
        
        # Filtro por responsável
        if filter_params.get('assigned_to'):
            if filter_params['assigned_to'] == 'me':
                # Filtrar tarefas atribuídas ao usuário atual
                # Implementar conforme necessário
                pass
            elif filter_params['assigned_to'] == 'unassigned':
                query = query.filter(Task.assignments_json == '{}')
            else:
                query = query.filter(Task.assignments_json.like(f'%"userId": "{filter_params["assigned_to"]}"%'))
        
        # Filtro por datas
        if filter_params.get('date_range'):
            date_range = filter_params['date_range']
            now = datetime.utcnow().date()
            
            if date_range == 'today':
                query = query.filter(func.date(Task.due_date) == now)
            elif date_range == 'this_week':
                start_week = now - timedelta(days=now.weekday())
                end_week = start_week + timedelta(days=6)
                query = query.filter(func.date(Task.due_date).between(start_week, end_week))
            elif date_range == 'overdue':
                query = query.filter(Task.is_overdue == True)
            elif date_range == 'next_7_days':
                end_date = now + timedelta(days=7)
                query = query.filter(func.date(Task.due_date) <= end_date)
        
        # Filtro por progresso
        if filter_params.get('progress'):
            progress = filter_params['progress']
            if progress == 'not_started':
                query = query.filter(Task.percent_complete == 0)
            elif progress == 'in_progress':
                query = query.filter(Task.percent_complete > 0, Task.percent_complete < 100)
            elif progress == 'completed':
                query = query.filter(Task.percent_complete == 100)
        
        # Filtro por labels/tags
        if filter_params.get('labels'):
            labels = filter_params['labels'].split(',')
            for label in labels:
                query = query.filter(Task.labels.like(f'%"{label}"%'))
        
        # Filtro por categoria
        if filter_params.get('category'):
            query = query.filter(Task.category == filter_params['category'])
        
        # Filtro por esforço
        if filter_params.get('effort'):
            try:
                effort = int(filter_params['effort'])
                query = query.filter(Task.effort == effort)
            except ValueError:
                pass
        
        # Filtro por valor de negócio
        if filter_params.get('business_value'):
            try:
                value = int(filter_params['business_value'])
                query = query.filter(Task.business_value == value)
            except ValueError:
                pass
        
        # Filtro de texto
        if filter_params.get('search'):
            search_term = f"%{filter_params['search']}%"
            query = query.filter(
                or_(
                    Task.title.ilike(search_term),
                    Task.description.ilike(search_term),
                    Task.blocked_reason.ilike(search_term)
                )
            )
        
        # Ordenação padrão
        query = query.order_by(Task.due_date.asc())
        
        return query
    
    @staticmethod
    def get_saved_filters(user_id):
        """Retorna filtros salvos do usuário"""
        from app.models import SavedFilter
        return SavedFilter.query.filter_by(user_id=user_id).all()
    
    @staticmethod
    def save_filter(user_id, name, description, filters, is_global=False):
        """Salva um novo filtro"""
        from app.models import SavedFilter, db
        
        saved_filter = SavedFilter(
            user_id=user_id,
            name=name,
            description=description,
            filters_json=json.dumps(filters),
            is_global=is_global
        )
        
        db.session.add(saved_filter)
        db.session.commit()
        
        return saved_filter