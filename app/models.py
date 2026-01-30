from app import db
from flask_login import UserMixin
from datetime import datetime, timezone
import json
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import event
import enum


class TaskStatus(enum.Enum):
    NOT_STARTED = 'not_started'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    OVERDUE = 'overdue'
    BLOCKED = 'blocked'

class TaskPriority(enum.Enum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    URGENT = 3

class NotificationType(enum.Enum):
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    SUCCESS = 'success'
    TASK_ASSIGNED = 'task_assigned'
    TASK_OVERDUE = 'task_overdue'
    TASK_COMPLETED = 'task_completed'

class ReportFrequency(enum.Enum):
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    QUARTERLY = 'quarterly'
    CUSTOM = 'custom'

class Theme(enum.Enum):
    LIGHT = 'light'
    DARK = 'dark'
    CORPORATE = 'corporate'

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    azure_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=True)
    display_name = db.Column(db.String(255))
    job_title = db.Column(db.String(255))
    department = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    
    # Autenticação
    access_token = db.Column(db.Text)
    refresh_token = db.Column(db.Text)
    token_expires = db.Column(db.DateTime)
    last_login = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    
    # Preferências
    preferences = db.Column(db.Text, default='{}')
    theme = db.Column(db.String(20), default='light')
    language = db.Column(db.String(10), default='pt-BR')
    timezone = db.Column(db.String(50), default='America/Sao_Paulo')
    
    # Configurações de notificação
    email_notifications = db.Column(db.Boolean, default=True)
    push_notifications = db.Column(db.Boolean, default=True)
    notification_frequency = db.Column(db.String(20), default='real_time')
    
    # Métricas
    total_tasks_assigned = db.Column(db.Integer, default=0)
    completed_tasks = db.Column(db.Integer, default=0)
    overdue_tasks = db.Column(db.Integer, default=0)
    
    # Relacionamentos
    dashboards = db.relationship('Dashboard', backref='user', lazy=True, cascade='all, delete-orphan')
    reports = db.relationship('Report', backref='user', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')
    saved_filters = db.relationship('SavedFilter', backref='user', lazy=True, cascade='all, delete-orphan')
    
    @hybrid_property
    def task_completion_rate(self):
        if self.total_tasks_assigned > 0:
            return (self.completed_tasks / self.total_tasks_assigned) * 100
        return 0
    
    def get_preferences(self):
        try:
            return json.loads(self.preferences) if self.preferences else {}
        except:
            return {}
    
    def set_preferences(self, preferences):
        self.preferences = json.dumps(preferences)
    
    def has_role(self, role):
        if role == 'admin':
            return self.is_admin
        return True

class Group(db.Model):
    __tablename__ = 'groups'
    
    id = db.Column(db.String(255), primary_key=True)
    name = db.Column(db.String(255))
    email = db.Column(db.String(255))
    description = db.Column(db.Text)
    group_type = db.Column(db.String(50))
    visibility = db.Column(db.String(50))
    created_date = db.Column(db.DateTime)
    last_sync = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)
    is_favorite = db.Column(db.Boolean, default=False)
    
    # Métricas
    total_planners = db.Column(db.Integer, default=0)
    total_tasks = db.Column(db.Integer, default=0)
    active_tasks = db.Column(db.Integer, default=0)
    
    # Relacionamentos
    planners = db.relationship('Planner', backref='group', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'description': self.description,
            'total_planners': self.total_planners,
            'total_tasks': self.total_tasks,
            'is_favorite': self.is_favorite
        }

class Planner(db.Model):
    __tablename__ = 'planners'
    
    id = db.Column(db.String(255), primary_key=True)
    group_id = db.Column(db.String(255), db.ForeignKey('groups.id'))
    title = db.Column(db.String(255))
    description = db.Column(db.Text)
    created_date = db.Column(db.DateTime)
    owner = db.Column(db.String(255))
    last_sync = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Configurações
    is_archived = db.Column(db.Boolean, default=False)
    is_favorite = db.Column(db.Boolean, default=False)
    color = db.Column(db.String(7), default='#3498db')  # Cor do planner
    
    # Métricas
    total_tasks = db.Column(db.Integer, default=0)
    completed_tasks = db.Column(db.Integer, default=0)
    in_progress_tasks = db.Column(db.Integer, default=0)
    not_started_tasks = db.Column(db.Integer, default=0)
    overdue_tasks = db.Column(db.Integer, default=0)
    blocked_tasks = db.Column(db.Integer, default=0)
    
    # Métricas calculadas
    @hybrid_property
    def completion_rate(self):
        if self.total_tasks > 0:
            return (self.completed_tasks / self.total_tasks) * 100
        return 0
    
    @hybrid_property
    def overdue_rate(self):
        if self.total_tasks > 0:
            return (self.overdue_tasks / self.total_tasks) * 100
        return 0
    
    # Relacionamentos
    tasks = db.relationship('Task', backref='planner', lazy=True, cascade='all, delete-orphan')
    buckets = db.relationship('Bucket', backref='planner', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'total_tasks': self.total_tasks,
            'completed_tasks': self.completed_tasks,
            'in_progress_tasks': self.in_progress_tasks,
            'overdue_tasks': self.overdue_tasks,
            'completion_rate': self.completion_rate,
            'overdue_rate': self.overdue_rate,
            'is_favorite': self.is_favorite,
            'color': self.color,
            'group_name': self.group.name if self.group else None
        }

class Bucket(db.Model):
    __tablename__ = 'buckets'
    
    id = db.Column(db.String(255), primary_key=True)
    planner_id = db.Column(db.String(255), db.ForeignKey('planners.id'))
    name = db.Column(db.String(255))
    order_hint = db.Column(db.String(50))
    
    # Métricas
    total_tasks = db.Column(db.Integer, default=0)
    
    # Relacionamentos
    tasks = db.relationship('Task', backref='bucket', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'planner_id': self.planner_id,
            'total_tasks': self.total_tasks
        }

class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.String(255), primary_key=True)
    planner_id = db.Column(db.String(255), db.ForeignKey('planners.id'))
    bucket_id = db.Column(db.String(255), db.ForeignKey('buckets.id'))
    
    # Informações básicas
    title = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    
    # Datas
    start_date = db.Column(db.DateTime)
    due_date = db.Column(db.DateTime)
    completed_date = db.Column(db.DateTime)
    created_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_modified = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                              onupdate=lambda: datetime.now(timezone.utc))
    
    # Status e progresso
    percent_complete = db.Column(db.Integer, default=0)
    status = db.Column(db.Enum(TaskStatus), default=TaskStatus.NOT_STARTED)
    priority = db.Column(db.Enum(TaskPriority), default=TaskPriority.MEDIUM)
    is_overdue = db.Column(db.Boolean, default=False)
    is_blocked = db.Column(db.Boolean, default=False)
    blocked_reason = db.Column(db.Text)
    
    # Labels e categorias
    labels = db.Column(db.Text)  # JSON array de labels
    category = db.Column(db.String(100))
    effort = db.Column(db.Integer)  # 1-5
    business_value = db.Column(db.Integer)  # 1-5
    
    # Assignments (armazenado como JSON)
    assignments_json = db.Column(db.Text)
    
    # Métricas
    checklists_total = db.Column(db.Integer, default=0)
    checklists_completed = db.Column(db.Integer, default=0)
    comments_count = db.Column(db.Integer, default=0)
    attachments_count = db.Column(db.Integer, default=0)
    time_estimate = db.Column(db.Integer)  # em horas
    time_spent = db.Column(db.Integer)  # em horas
    
    @hybrid_property
    def checklist_completion(self):
        if self.checklists_total > 0:
            return (self.checklists_completed / self.checklists_total) * 100
        return 100
    
    @hybrid_property
    def days_until_due(self):
        """Calcula dias até o vencimento, tratando timezone corretamente"""
        if self.due_date:
            # Garantir que ambos os datetimes tenham timezone
            now = datetime.now(timezone.utc)
            
            # Se due_date não tem timezone (naive), assume UTC
            if self.due_date.tzinfo is None:
                due_date_aware = self.due_date.replace(tzinfo=timezone.utc)
            else:
                due_date_aware = self.due_date
            
            delta = due_date_aware - now
            return delta.days
        return None
    
    @hybrid_property
    def is_urgent(self):
        """Verifica se tarefa é urgente (vence em 2 dias ou menos)"""
        if not self.due_date:
            return False
        days = self.days_until_due
        return days is not None and days <= 2 and self.status != TaskStatus.COMPLETED
    
    def get_labels(self):
        try:
            return json.loads(self.labels) if self.labels else []
        except:
            return []
    
    def set_labels(self, labels):
        self.labels = json.dumps(labels)
    
    def get_assignments(self):
        try:
            return json.loads(self.assignments_json) if self.assignments_json else {}
        except:
            return {}
    
    def set_assignments(self, assignments):
        self.assignments_json = json.dumps(assignments)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'status': self.status.value if self.status else None,
            'priority': self.priority.value if self.priority else None,
            'percent_complete': self.percent_complete,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'is_overdue': self.is_overdue,
            'is_urgent': self.is_urgent,
            'assignments': self.get_assignments(),
            'planner_title': self.planner.title if self.planner else None,
            'bucket_name': self.bucket.name if self.bucket else None
        }
    
    # Relacionamentos
    comments = db.relationship('TaskComment', backref='task', lazy=True, cascade='all, delete-orphan')
    changes = db.relationship('TaskChange', backref='task', lazy=True, cascade='all, delete-orphan')
    attachments = db.relationship('TaskAttachment', backref='task', lazy=True, cascade='all, delete-orphan')
    checklists = db.relationship('TaskChecklist', backref='task', lazy=True, cascade='all, delete-orphan')

class TaskComment(db.Model):
    __tablename__ = 'task_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(255), db.ForeignKey('tasks.id'))
    user_id = db.Column(db.String(255))
    user_name = db.Column(db.String(255))
    user_email = db.Column(db.String(255))
    comment = db.Column(db.Text)
    created_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    modified_date = db.Column(db.DateTime)
    is_edited = db.Column(db.Boolean, default=False)
    
    # Metadados
    mentions = db.Column(db.Text)  # JSON array de menções
    reactions = db.Column(db.Text)  # JSON de reações
    
    def get_mentions(self):
        try:
            return json.loads(self.mentions) if self.mentions else []
        except:
            return []
    
    def get_reactions(self):
        try:
            return json.loads(self.reactions) if self.reactions else {}
        except:
            return {}

class TaskChange(db.Model):
    __tablename__ = 'task_changes'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(255), db.ForeignKey('tasks.id'))
    field_changed = db.Column(db.String(100))
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    changed_by = db.Column(db.String(255))
    changed_by_name = db.Column(db.String(255))
    changed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    change_type = db.Column(db.String(50))  # 'created', 'updated', 'deleted', 'status_change', etc.

class TaskAttachment(db.Model):
    __tablename__ = 'task_attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(255), db.ForeignKey('tasks.id'))
    filename = db.Column(db.String(500))
    filepath = db.Column(db.String(500))
    file_type = db.Column(db.String(100))
    file_size = db.Column(db.Integer)  # em bytes
    uploaded_by = db.Column(db.String(255))
    uploaded_by_name = db.Column(db.String(255))
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    description = db.Column(db.Text)
    download_count = db.Column(db.Integer, default=0)

class TaskChecklist(db.Model):
    __tablename__ = 'task_checklists'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(255), db.ForeignKey('tasks.id'))
    title = db.Column(db.String(500))
    is_completed = db.Column(db.Boolean, default=False)
    created_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_date = db.Column(db.DateTime)
    order = db.Column(db.Integer, default=0)

class SavedFilter(db.Model):
    __tablename__ = 'saved_filters'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(255))
    description = db.Column(db.Text)
    filters_json = db.Column(db.Text)  # JSON com critérios do filtro
    is_global = db.Column(db.Boolean, default=False)  # Filtro compartilhado
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_used = db.Column(db.DateTime)
    usage_count = db.Column(db.Integer, default=0)
    
    def get_filters(self):
        try:
            return json.loads(self.filters_json) if self.filters_json else {}
        except:
            return {}
    
    def set_filters(self, filters):
        self.filters_json = json.dumps(filters)

class Dashboard(db.Model):
    __tablename__ = 'dashboards'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(255))
    description = db.Column(db.Text)
    layout_config = db.Column(db.Text)  # JSON configuration
    is_default = db.Column(db.Boolean, default=False)
    is_public = db.Column(db.Boolean, default=False)
    theme = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc))
    
    # Relacionamentos
    widgets = db.relationship('DashboardWidget', backref='dashboard', lazy=True, 
                              cascade='all, delete-orphan')
    
    def get_layout_config(self):
        try:
            return json.loads(self.layout_config) if self.layout_config else {}
        except:
            return {}

class DashboardWidget(db.Model):
    __tablename__ = 'dashboard_widgets'
    
    id = db.Column(db.Integer, primary_key=True)
    dashboard_id = db.Column(db.Integer, db.ForeignKey('dashboards.id'))
    widget_type = db.Column(db.String(50))
    title = db.Column(db.String(255))
    config = db.Column(db.Text)  # JSON configuration
    data_source = db.Column(db.Text)  # JSON com query ou filtro
    refresh_interval = db.Column(db.Integer)  # segundos
    position_x = db.Column(db.Integer)
    position_y = db.Column(db.Integer)
    width = db.Column(db.Integer, default=4)
    height = db.Column(db.Integer, default=3)
    display_order = db.Column(db.Integer, default=0)
    is_visible = db.Column(db.Boolean, default=True)
    last_refresh = db.Column(db.DateTime)
    
    def get_config(self):
        try:
            return json.loads(self.config) if self.config else {}
        except:
            return {}
    
    def get_data_source(self):
        try:
            return json.loads(self.data_source) if self.data_source else {}
        except:
            return {}

class Report(db.Model):
    __tablename__ = 'reports'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(255))
    description = db.Column(db.Text)
    report_type = db.Column(db.String(50))
    report_format = db.Column(db.String(20), default='excel')  # 'excel', 'pdf', 'csv', 'html'
    filters = db.Column(db.Text)  # JSON filters
    schedule = db.Column(db.Enum(ReportFrequency), default=ReportFrequency.CUSTOM)
    schedule_config = db.Column(db.Text)  # JSON com configurações do schedule
    recipients = db.Column(db.Text)  # JSON array de emails
    last_run = db.Column(db.DateTime)
    next_run = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc))
    
    # Relacionamentos
    report_runs = db.relationship('ReportRun', backref='report', lazy=True, 
                                 cascade='all, delete-orphan')
    
    def get_filters(self):
        try:
            return json.loads(self.filters) if self.filters else {}
        except:
            return {}
    
    def get_recipients(self):
        try:
            return json.loads(self.recipients) if self.recipients else []
        except:
            return []
    
    def get_schedule_config(self):
        try:
            return json.loads(self.schedule_config) if self.schedule_config else {}
        except:
            return {}

class ReportRun(db.Model):
    __tablename__ = 'report_runs'
    
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('reports.id'))
    status = db.Column(db.String(20))  # 'pending', 'running', 'completed', 'failed'
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime)
    duration = db.Column(db.Integer)  # segundos
    result_path = db.Column(db.String(500))
    error_message = db.Column(db.Text)
    records_processed = db.Column(db.Integer)
    file_size = db.Column(db.Integer)

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    title = db.Column(db.String(255))
    message = db.Column(db.Text)
    notification_type = db.Column(db.Enum(NotificationType), default=NotificationType.INFO)
    is_read = db.Column(db.Boolean, default=False)
    is_archived = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    read_at = db.Column(db.DateTime)
    
    # Ações
    action_url = db.Column(db.String(500))
    action_text = db.Column(db.String(100))
    action_data = db.Column(db.Text)  # JSON data
    
    # Relacionamento com entidades
    entity_type = db.Column(db.String(50))  # 'task', 'planner', 'group'
    entity_id = db.Column(db.String(255))
    
    def get_action_data(self):
        try:
            return json.loads(self.action_data) if self.action_data else {}
        except:
            return {}

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    activity_type = db.Column(db.String(50))
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Dados adicionais - RENOMEADO para 'log_data'
    log_data = db.Column(db.Text)  # JSON com dados adicionais
    severity = db.Column(db.String(20), default='info')  # 'info', 'warning', 'error'
    
    def get_log_data(self):
        try:
            return json.loads(self.log_data) if self.log_data else {}
        except:
            return {}

class EmailTemplate(db.Model):
    __tablename__ = 'email_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)
    subject = db.Column(db.String(255))
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    template_type = db.Column(db.String(50))
    variables = db.Column(db.Text)  # JSON com variáveis disponíveis
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc))
    
    def get_variables(self):
        try:
            return json.loads(self.variables) if self.variables else []
        except:
            return []

class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(20))  # 'string', 'integer', 'boolean', 'json'
    category = db.Column(db.String(50))
    description = db.Column(db.Text)
    is_public = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc))
    
    def get_value(self):
        if self.value_type == 'json':
            try:
                return json.loads(self.value) if self.value else {}
            except:
                return self.value
        elif self.value_type == 'integer':
            return int(self.value) if self.value else 0
        elif self.value_type == 'boolean':
            return self.value.lower() == 'true'
        else:
            return self.value