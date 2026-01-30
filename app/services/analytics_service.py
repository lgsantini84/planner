import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import func, desc, extract
import json

class AnalyticsService:
    def __init__(self, db_session):
        self.db = db_session
    
    def get_task_distribution_chart(self, user_id=None, group_id=None):
        """Gráfico de distribuição de tarefas"""
        from app.models import Task, TaskStatus, Planner
        
        query = self.db.session.query(Task.status, func.count(Task.id).label('count'))
        
        if user_id:
            # Filtrar tarefas do usuário
            pass
        
        if group_id:
            query = query.join(Planner).filter(Planner.group_id == group_id)
        
        results = query.group_by(Task.status).all()
        
        status_names = {
            TaskStatus.NOT_STARTED: 'Não Iniciada',
            TaskStatus.IN_PROGRESS: 'Em Progresso',
            TaskStatus.COMPLETED: 'Concluída',
            TaskStatus.OVERDUE: 'Atrasada',
            TaskStatus.BLOCKED: 'Bloqueada'
        }
        
        labels = [status_names.get(status, str(status)) for status, _ in results]
        values = [count for _, count in results]
        
        colors = ['#6c757d', '#ffc107', '#28a745', '#dc3545', '#e74c3c']
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=.3,
            marker=dict(colors=colors),
            textinfo='label+percent',
            insidetextorientation='radial'
        )])
        
        fig.update_layout(
            title_text='Distribuição por Status',
            showlegend=True,
            height=400,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def get_completion_trend_chart(self, days=30):
        """Gráfico de tendência de conclusão"""
        from app.models import Task, TaskStatus
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Consulta para tarefas concluídas por dia
        completed_tasks = self.db.session.query(
            func.date(Task.completed_date).label('date'),
            func.count(Task.id).label('count')
        ).filter(
            Task.completed_date.between(start_date, end_date),
            Task.status == TaskStatus.COMPLETED  # CORREÇÃO: usar enum
        ).group_by(func.date(Task.completed_date)).all()
        
        # Criar DataFrame com todos os dias
        date_range = pd.date_range(start=start_date.date(), end=end_date.date())
        df = pd.DataFrame({'date': date_range})
        
        # Adicionar contagens
        completed_dict = {date: count for date, count in completed_tasks}
        df['completed'] = df['date'].apply(lambda x: completed_dict.get(x, 0))
        df['cumulative'] = df['completed'].cumsum()
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['completed'],
            mode='lines+markers',
            name='Concluídas por dia',
            line=dict(color='#28a745', width=2),
            marker=dict(size=8)
        ))
        
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['cumulative'],
            mode='lines',
            name='Total acumulado',
            line=dict(color='#3498db', width=2, dash='dash'),
            yaxis='y2'
        ))
        
        fig.update_layout(
            title_text=f'Tendência de Conclusão (Últimos {days} dias)',
            xaxis_title='Data',
            yaxis_title='Tarefas Concluídas',
            yaxis2=dict(
                title='Total Acumulado',
                overlaying='y',
                side='right'
            ),
            height=400,
            hovermode='x unified'
        )
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def get_workload_chart(self):
        """Gráfico de workload por usuário"""
        from app.models import Task, User
        
        # Consulta para tarefas por usuário
        workload_data = []
        users = User.query.filter_by(is_active=True).all()
        
        for user in users:
            # Contar tarefas por status
            tasks = Task.query.filter(
                Task.assignments_json.like(f'%"userId": "{user.azure_id}"%')
            ).all()
            
            if tasks:
                workload_data.append({
                    'user': user.display_name,
                    'total': len(tasks),
                    'completed': sum(1 for t in tasks if t.status == 'completed'),
                    'in_progress': sum(1 for t in tasks if t.status == 'in_progress'),
                    'overdue': sum(1 for t in tasks if t.is_overdue)
                })
        
        df = pd.DataFrame(workload_data)
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=df['user'],
            y=df['completed'],
            name='Concluídas',
            marker_color='#28a745'
        ))
        
        fig.add_trace(go.Bar(
            x=df['user'],
            y=df['in_progress'],
            name='Em Progresso',
            marker_color='#ffc107'
        ))
        
        fig.add_trace(go.Bar(
            x=df['user'],
            y=df['overdue'],
            name='Atrasadas',
            marker_color='#dc3545'
        ))
        
        fig.update_layout(
            title_text='Workload por Usuário',
            xaxis_title='Usuário',
            yaxis_title='Número de Tarefas',
            barmode='stack',
            height=500,
            xaxis_tickangle=-45
        )
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def get_burndown_chart(self, planner_id):
        """Gráfico de burndown para um planner"""
        from app.models import Task, Planner
        
        planner = Planner.query.get(planner_id)
        if not planner:
            return None
        
        tasks = Task.query.filter_by(planner_id=planner_id).all()
        
        # Calcular burndown
        start_date = min(t.created_date for t in tasks if t.created_date)
        end_date = max(t.due_date for t in tasks if t.due_date)
        
        if not start_date or not end_date:
            return None
        
        # Implementar lógica de burndown
        # ...
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def get_kpis(self, user_id=None):
        """Retorna KPIs principais"""
        from app.models import Task, Planner, Group
        
        total_tasks = Task.query.count()
        completed_tasks = Task.query.filter_by(status='completed').count()
        overdue_tasks = Task.query.filter_by(is_overdue=True).count()
        in_progress_tasks = Task.query.filter_by(status='in_progress').count()
        
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Tarefas criadas hoje
        today = datetime.now().date()
        today_tasks = Task.query.filter(
            func.date(Task.created_date) == today
        ).count()
        
        # Tarefas vencendo hoje
        due_today = Task.query.filter(
            func.date(Task.due_date) == today,
            Task.status != 'completed'
        ).count()
        
        return {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'overdue_tasks': overdue_tasks,
            'in_progress_tasks': in_progress_tasks,
            'completion_rate': f"{completion_rate:.1f}%",
            'today_tasks': today_tasks,
            'due_today': due_today,
            'total_planners': Planner.query.count(),
            'total_groups': Group.query.count()
        }