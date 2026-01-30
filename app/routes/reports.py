from flask import Blueprint, render_template, request, jsonify, send_file, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import json
from io import BytesIO

from app.models import db, Report, ReportRun, SavedFilter, Planner, Group, Task
from app.services.report_service import ReportService
from app.services.email_service import EmailService
from app.services.analytics_service import AnalyticsService
from app.utils.decorators import admin_required

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/')
@login_required
def list_reports():
    """Lista de relatórios disponíveis"""
    try:
        user_reports = Report.query.filter_by(user_id=current_user.id).order_by(Report.created_at.desc()).all()
        system_reports = Report.query.filter_by(is_global=True).order_by(Report.name).all()
        
        # Relatórios pré-configurados
        predefined_reports = [
            {
                'id': 'tasks_summary',
                'name': 'Resumo de Tarefas',
                'description': 'Visão geral de todas as tarefas',
                'icon': 'fa-tasks'
            },
            {
                'id': 'performance',
                'name': 'Performance da Equipe',
                'description': 'Desempenho por usuário e planner',
                'icon': 'fa-chart-line'
            },
            {
                'id': 'overdue_analysis',
                'name': 'Análise de Atrasos',
                'description': 'Tarefas atrasadas e causas',
                'icon': 'fa-clock'
            },
            {
                'id': 'workload_distribution',
                'name': 'Distribuição de Workload',
                'description': 'Carga de trabalho por usuário',
                'icon': 'fa-balance-scale'
            }
        ]
        
        return render_template('reports/list.html',
                             user_reports=user_reports,
                             system_reports=system_reports,
                             predefined_reports=predefined_reports)
        
    except Exception as e:
        flash(f'Erro ao carregar relatórios: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@reports_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_report():
    """Cria um novo relatório"""
    try:
        if request.method == 'POST':
            data = request.form
            
            # Criar configurações do relatório
            report_config = {
                'name': data.get('name'),
                'description': data.get('description'),
                'report_type': data.get('report_type'),
                'filters': json.loads(data.get('filters', '{}')),
                'schedule': data.get('schedule'),
                'recipients': data.get('recipients', '').split(','),
                'format': data.get('format', 'excel')
            }
            
            # Criar relatório no banco
            report = Report(
                user_id=current_user.id,
                name=report_config['name'],
                description=report_config['description'],
                report_type=report_config['report_type'],
                report_format=report_config['format'],
                filters=json.dumps(report_config['filters']),
                schedule=report_config['schedule'],
                recipients=json.dumps(report_config['recipients']),
                is_active=True
            )
            
            db.session.add(report)
            db.session.commit()
            
            flash('Relatório criado com sucesso!', 'success')
            return redirect(url_for('reports.list_reports'))
        
        # GET - Mostrar formulário
        planners = Planner.query.all()
        groups = Group.query.filter_by(is_active=True).all()
        saved_filters = SavedFilter.query.filter_by(user_id=current_user.id).all()
        
        return render_template('reports/create.html',
                             planners=planners,
                             groups=groups,
                             saved_filters=saved_filters)
        
    except Exception as e:
        flash(f'Erro ao criar relatório: {str(e)}', 'error')
        return redirect(url_for('reports.list_reports'))

@reports_bp.route('/<int:report_id>/run', methods=['POST'])
@login_required
def run_report(report_id):
    """Executa um relatório"""
    try:
        report = Report.query.get_or_404(report_id)
        
        # Verificar permissão
        if report.user_id != current_user.id and not report.is_global:
            flash('Você não tem permissão para executar este relatório.', 'error')
            return redirect(url_for('reports.list_reports'))
        
        # Criar registro de execução
        report_run = ReportRun(
            report_id=report.id,
            status='running',
            started_at=datetime.utcnow()
        )
        db.session.add(report_run)
        db.session.commit()
        
        # Executar relatório em background (usando Celery)
        from app.tasks import run_report_task
        run_report_task.delay(report_id, report_run.id, current_user.id)
        
        flash('Relatório está sendo gerado. Você será notificado quando estiver pronto.', 'info')
        return redirect(url_for('reports.report_status', report_id=report_id, run_id=report_run.id))
        
    except Exception as e:
        flash(f'Erro ao executar relatório: {str(e)}', 'error')
        return redirect(url_for('reports.list_reports'))

@reports_bp.route('/<int:report_id>/run/<int:run_id>/status')
@login_required
def report_status(report_id, run_id):
    """Verifica status da execução do relatório"""
    try:
        report_run = ReportRun.query.get_or_404(run_id)
        report = Report.query.get_or_404(report_id)
        
        # Verificar permissão
        if report.user_id != current_user.id and not report.is_global:
            flash('Acesso não autorizado.', 'error')
            return redirect(url_for('reports.list_reports'))
        
        return render_template('reports/status.html',
                             report=report,
                             report_run=report_run)
        
    except Exception as e:
        flash(f'Erro ao verificar status: {str(e)}', 'error')
        return redirect(url_for('reports.list_reports'))

@reports_bp.route('/<int:report_id>/run/<int:run_id>/download')
@login_required
def download_report(report_id, run_id):
    """Download do relatório gerado"""
    try:
        report_run = ReportRun.query.get_or_404(run_id)
        report = Report.query.get_or_404(report_id)
        
        # Verificar permissão
        if report.user_id != current_user.id and not report.is_global:
            flash('Acesso não autorizado.', 'error')
            return redirect(url_for('reports.list_reports'))
        
        if report_run.status != 'completed' or not report_run.result_path:
            flash('Relatório não está disponível para download.', 'error')
            return redirect(url_for('reports.report_status', report_id=report_id, run_id=run_id))
        
        return send_file(
            report_run.result_path,
            as_attachment=True,
            download_name=f"{report.name}_{report_run.started_at.strftime('%Y%m%d_%H%M%S')}.{report.report_format}"
        )
        
    except Exception as e:
        flash(f'Erro ao baixar relatório: {str(e)}', 'error')
        return redirect(url_for('reports.list_reports'))

@reports_bp.route('/<int:report_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_report(report_id):
    """Edita um relatório existente"""
    try:
        report = Report.query.get_or_404(report_id)
        
        # Verificar permissão
        if report.user_id != current_user.id:
            flash('Você não tem permissão para editar este relatório.', 'error')
            return redirect(url_for('reports.list_reports'))
        
        if request.method == 'POST':
            data = request.form
            
            report.name = data.get('name')
            report.description = data.get('description')
            report.report_type = data.get('report_type')
            report.filters = data.get('filters', '{}')
            report.schedule = data.get('schedule')
            report.recipients = json.dumps(data.get('recipients', '').split(','))
            report.report_format = data.get('format', 'excel')
            report.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash('Relatório atualizado com sucesso!', 'success')
            return redirect(url_for('reports.list_reports'))
        
        # GET - Mostrar formulário
        planners = Planner.query.all()
        groups = Group.query.filter_by(is_active=True).all()
        saved_filters = SavedFilter.query.filter_by(user_id=current_user.id).all()
        
        return render_template('reports/edit.html',
                             report=report,
                             planners=planners,
                             groups=groups,
                             saved_filters=saved_filters)
        
    except Exception as e:
        flash(f'Erro ao editar relatório: {str(e)}', 'error')
        return redirect(url_for('reports.list_reports'))

@reports_bp.route('/<int:report_id>/delete', methods=['POST'])
@login_required
def delete_report(report_id):
    """Exclui um relatório"""
    try:
        report = Report.query.get_or_404(report_id)
        
        # Verificar permissão
        if report.user_id != current_user.id:
            flash('Você não tem permissão para excluir este relatório.', 'error')
            return redirect(url_for('reports.list_reports'))
        
        # Excluir execuções do relatório
        ReportRun.query.filter_by(report_id=report_id).delete()
        
        # Excluir relatório
        db.session.delete(report)
        db.session.commit()
        
        flash('Relatório excluído com sucesso!', 'success')
        return redirect(url_for('reports.list_reports'))
        
    except Exception as e:
        flash(f'Erro ao excluir relatório: {str(e)}', 'error')
        return redirect(url_for('reports.list_reports'))

@reports_bp.route('/predefined/<report_type>')
@login_required
def predefined_report(report_type):
    """Gera um relatório pré-definido"""
    try:
        report_service = ReportService(current_user)
        
        if report_type == 'tasks_summary':
            filters = request.args.to_dict()
            report_data = report_service.generate_task_report(filters)
            
            # Gerar gráficos
            analytics = AnalyticsService(db)
            status_chart = analytics.get_task_distribution_chart()
            trend_chart = analytics.get_completion_trend_chart()
            
            return render_template('reports/predefined/tasks_summary.html',
                                 report_data=report_data,
                                 status_chart=status_chart,
                                 trend_chart=trend_chart,
                                 filters=filters)
            
        elif report_type == 'performance':
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            
            if not start_date:
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            
            report_data = report_service.generate_performance_report(start_date, end_date)
            
            return render_template('reports/predefined/performance.html',
                                 report_data=report_data,
                                 start_date=start_date,
                                 end_date=end_date)
            
        else:
            flash('Tipo de relatório não suportado.', 'error')
            return redirect(url_for('reports.list_reports'))
        
    except Exception as e:
        flash(f'Erro ao gerar relatório: {str(e)}', 'error')
        return redirect(url_for('reports.list_reports'))

@reports_bp.route('/api/export', methods=['POST'])
@login_required
def export_report():
    """Exporta relatório via API"""
    try:
        data = request.get_json()
        report_type = data.get('type')
        filters = data.get('filters', {})
        format = data.get('format', 'excel')
        
        report_service = ReportService(current_user)
        
        if report_type == 'tasks':
            report_data = report_service.generate_task_report(filters)
        elif report_type == 'performance':
            report_data = report_service.generate_performance_report(
                filters.get('start_date'),
                filters.get('end_date')
            )
        else:
            return jsonify({'success': False, 'error': 'Tipo de relatório inválido'}), 400
        
        # Exportar para o formato solicitado
        if format == 'excel':
            output = report_service.export_to_excel(report_data, 'relatorio.xlsx')
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='relatorio.xlsx'
            )
        else:
            return jsonify({'success': False, 'error': 'Formato não suportado'}), 400
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@reports_bp.route('/schedule', methods=['POST'])
@login_required
def schedule_report():
    """Agenda execução automática de relatório"""
    try:
        data = request.get_json()
        report_id = data.get('report_id')
        schedule = data.get('schedule')
        
        report = Report.query.get_or_404(report_id)
        
        # Verificar permissão
        if report.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Permissão negada'}), 403
        
        report.schedule = schedule
        report.updated_at = datetime.utcnow()
        
        # Calcular próxima execução
        if schedule != 'none':
            report.next_run = calculate_next_run(schedule)
        
        db.session.commit()
        
        return jsonify({'success': True, 'next_run': report.next_run})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def calculate_next_run(schedule):
    """Calcula a próxima execução baseada no schedule"""
    now = datetime.utcnow()
    
    if schedule == 'daily':
        return now + timedelta(days=1)
    elif schedule == 'weekly':
        return now + timedelta(weeks=1)
    elif schedule == 'monthly':
        # Primeiro dia do próximo mês
        if now.month == 12:
            return datetime(now.year + 1, 1, 1)
        else:
            return datetime(now.year, now.month + 1, 1)
    elif schedule == 'quarterly':
        # Próximo trimestre
        quarter = (now.month - 1) // 3 + 1
        next_quarter = quarter + 1 if quarter < 4 else 1
        year = now.year if quarter < 4 else now.year + 1
        
        if next_quarter == 1:
            return datetime(year, 1, 1)
        elif next_quarter == 2:
            return datetime(year, 4, 1)
        elif next_quarter == 3:
            return datetime(year, 7, 1)
        else:  # next_quarter == 4
            return datetime(year, 10, 1)
    
    return None