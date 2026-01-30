# app/routes/planners.py
from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from app.models import Planner, Group, Task

planners_bp = Blueprint('planners', __name__, url_prefix='/planners')

@planners_bp.route('/')
@login_required
def list_planners():
    """Lista de planners"""
    planners = Planner.query.all()
    groups = Group.query.filter_by(is_active=True).all()
    
    return render_template('planners/list.html',
                         planners=planners,
                         groups=groups)

@planners_bp.route('/<planner_id>')
@login_required
def planner_detail(planner_id):
    """Detalhes do planner"""
    planner = Planner.query.get_or_404(planner_id)
    tasks = Task.query.filter_by(planner_id=planner_id).all()
    
    return render_template('planners/detail.html',
                         planner=planner,
                         tasks=tasks)

@planners_bp.route('/api/<planner_id>/stats')
@login_required
def planner_stats(planner_id):
    """API para estatísticas do planner"""
    from sqlalchemy import func
    
    planner = Planner.query.get_or_404(planner_id)
    
    # Estatísticas por status
    from app.models import TaskStatus
    status_stats = {
        'not_started': 0,
        'in_progress': 0,
        'completed': 0,
        'overdue': 0
    }
    
    for task in planner.tasks:
        if task.status == TaskStatus.NOT_STARTED:
            status_stats['not_started'] += 1
        elif task.status == TaskStatus.IN_PROGRESS:
            status_stats['in_progress'] += 1
        elif task.status == TaskStatus.COMPLETED:
            status_stats['completed'] += 1
        if task.is_overdue:
            status_stats['overdue'] += 1
    
    return jsonify({
        'success': True,
        'stats': status_stats,
        'planner': {
            'id': planner.id,
            'title': planner.title,
            'completion_rate': planner.completion_rate
        }
    })