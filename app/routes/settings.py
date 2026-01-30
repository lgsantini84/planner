from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
import json

from app.models import db, User, SystemSetting, Theme
from app.services.email_service import EmailService
from app.utils.decorators import admin_required

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

@settings_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Configurações de perfil do usuário"""
    try:
        if request.method == 'POST':
            # Atualizar perfil
            current_user.display_name = request.form.get('display_name')
            current_user.job_title = request.form.get('job_title')
            current_user.department = request.form.get('department')
            current_user.phone = request.form.get('phone')
            current_user.timezone = request.form.get('timezone')
            current_user.language = request.form.get('language')
            
            # Atualizar email (se fornecido e diferente)
            new_email = request.form.get('email')
            if new_email and new_email != current_user.email:
                # Verificar se email já existe
                existing_user = User.query.filter_by(email=new_email).first()
                if existing_user and existing_user.id != current_user.id:
                    flash('Este email já está em uso.', 'error')
                else:
                    current_user.email = new_email
            
            db.session.commit()
            flash('Perfil atualizado com sucesso!', 'success')
            return redirect(url_for('settings.profile'))
        
        return render_template('settings/profile.html')
        
    except Exception as e:
        flash(f'Erro ao atualizar perfil: {str(e)}', 'error')
        return redirect(url_for('settings.profile'))

@settings_bp.route('/preferences', methods=['GET', 'POST'])
@login_required
def preferences():
    """Preferências do usuário"""
    try:
        if request.method == 'POST':
            # Atualizar preferências
            preferences = current_user.get_preferences()
            
            # Configurações de UI
            current_user.theme = request.form.get('theme', 'light')
            preferences['items_per_page'] = int(request.form.get('items_per_page', 50))
            preferences['default_view'] = request.form.get('default_view', 'dashboard')
            preferences['compact_mode'] = 'compact_mode' in request.form
            
            # Configurações de notificação
            current_user.email_notifications = 'email_notifications' in request.form
            current_user.push_notifications = 'push_notifications' in request.form
            current_user.notification_frequency = request.form.get('notification_frequency', 'real_time')
            
            # Configurações de relatório
            preferences['report_format'] = request.form.get('report_format', 'excel')
            preferences['auto_refresh'] = int(request.form.get('auto_refresh', 0))
            
            current_user.set_preferences(preferences)
            db.session.commit()
            
            flash('Preferências atualizadas com sucesso!', 'success')
            return redirect(url_for('settings.preferences'))
        
        return render_template('settings/preferences.html',
                             themes=Theme,
                             preferences=current_user.get_preferences())
        
    except Exception as e:
        flash(f'Erro ao atualizar preferências: {str(e)}', 'error')
        return redirect(url_for('settings.preferences'))

@settings_bp.route('/notifications')
@login_required
def notifications():
    """Gerenciamento de notificações"""
    try:
        from app.models import Notification
        from app.services.notification_service import NotificationService
        
        notification_service = NotificationService()
        
        # Paginação
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Filtros
        show_read = request.args.get('show_read', 'false') == 'true'
        notification_type = request.args.get('type')
        
        query = Notification.query.filter_by(user_id=current_user.id)
        
        if not show_read:
            query = query.filter_by(is_read=False)
        
        if notification_type:
            query = query.filter_by(notification_type=notification_type)
        
        notifications = query.order_by(Notification.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Estatísticas
        unread_count = notification_service.get_unread_count(current_user.id)
        total_count = Notification.query.filter_by(user_id=current_user.id).count()
        
        return render_template('settings/notifications.html',
                             notifications=notifications,
                             unread_count=unread_count,
                             total_count=total_count)
        
    except Exception as e:
        flash(f'Erro ao carregar notificações: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@settings_bp.route('/api/notifications/mark-read', methods=['POST'])
@login_required
def mark_notification_read():
    """Marca notificação como lida"""
    try:
        from app.services.notification_service import NotificationService
        
        data = request.get_json()
        notification_id = data.get('notification_id')
        
        notification_service = NotificationService()
        
        if notification_id == 'all':
            success = notification_service.mark_all_as_read(current_user.id)
        else:
            success = notification_service.mark_as_read(notification_id, current_user.id)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Notificação não encontrada'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/api/notifications/clear-all', methods=['POST'])
@login_required
def clear_all_notifications():
    """Limpa todas as notificações"""
    try:
        from app.models import Notification
        
        Notification.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/security')
@login_required
def security():
    """Configurações de segurança"""
    return render_template('settings/security.html')

@settings_bp.route('/api/sessions')
@login_required
def get_sessions():
    """Obtém sessões ativas do usuário"""
    try:
        # Implementar rastreamento de sessões
        sessions = [
            {
                'id': 'current',
                'ip_address': request.remote_addr,
                'user_agent': request.user_agent.string,
                'last_activity': datetime.now().isoformat(),
                'current': True
            }
        ]
        
        return jsonify({'success': True, 'sessions': sessions})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/api/sessions/<session_id>/revoke', methods=['POST'])
@login_required
def revoke_session(session_id):
    """Revoga uma sessão"""
    try:
        # Implementar revogação de sessões
        # Para Flask-Login, você pode invalidar tokens específicos
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/integrations')
@login_required
def integrations():
    """Configurações de integração"""
    return render_template('settings/integrations.html')

@settings_bp.route('/api/test-email', methods=['POST'])
@login_required
def test_email():
    """Testa configuração de email"""
    try:
        if not current_user.email:
            return jsonify({'success': False, 'error': 'Email não configurado'}), 400
        
        email_service = EmailService()
        
        # Enviar email de teste
        success = email_service.send_email(
            to_emails=[current_user.email],
            subject='Teste de Email - Planner Dashboard',
            body_html='<h2>Teste de Email</h2><p>Este é um email de teste enviado pelo Planner Dashboard.</p>',
            body_text='Teste de Email - Este é um email de teste enviado pelo Planner Dashboard.'
        )
        
        if success:
            return jsonify({'success': True, 'message': 'Email de teste enviado com sucesso!'})
        else:
            return jsonify({'success': False, 'error': 'Falha ao enviar email'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/system', methods=['GET', 'POST'])
@admin_required
def system_settings():
    """Configurações do sistema (admin)"""
    try:
        if request.method == 'POST':
            # Atualizar configurações do sistema
            settings_data = request.form
            
            for key, value in settings_data.items():
                if key.startswith('setting_'):
                    setting_key = key.replace('setting_', '')
                    setting = SystemSetting.query.filter_by(key=setting_key).first()
                    
                    if setting:
                        setting.value = value
                        setting.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash('Configurações do sistema atualizadas com sucesso!', 'success')
            return redirect(url_for('settings.system_settings'))
        
        # GET - Mostrar configurações
        system_settings = SystemSetting.query.all()
        settings_dict = {s.key: s for s in system_settings}
        
        return render_template('settings/system.html',
                             settings=settings_dict)
        
    except Exception as e:
        flash(f'Erro ao atualizar configurações do sistema: {str(e)}', 'error')
        return redirect(url_for('settings.system_settings'))

@settings_bp.route('/backup')
@admin_required
def backup():
    """Backup do sistema"""
    try:
        # Listar backups disponíveis
        import os
        from app.config import BACKUP_FOLDER
        
        backups = []
        if os.path.exists(BACKUP_FOLDER):
            for file in os.listdir(BACKUP_FOLDER):
                if file.endswith('.sql') or file.endswith('.backup'):
                    filepath = os.path.join(BACKUP_FOLDER, file)
                    stats = os.stat(filepath)
                    
                    backups.append({
                        'filename': file,
                        'size': stats.st_size,
                        'created': datetime.fromtimestamp(stats.st_ctime),
                        'modified': datetime.fromtimestamp(stats.st_mtime)
                    })
        
        backups.sort(key=lambda x: x['created'], reverse=True)
        
        return render_template('settings/backup.html',
                             backups=backups)
        
    except Exception as e:
        flash(f'Erro ao carregar backups: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@settings_bp.route('/api/backup/create', methods=['POST'])
@admin_required
def create_backup():
    """Cria backup do banco de dados"""
    try:
        from app.utils.backup import create_database_backup
        
        backup_file = create_database_backup()
        
        if backup_file:
            return jsonify({
                'success': True,
                'message': 'Backup criado com sucesso!',
                'filename': os.path.basename(backup_file)
            })
        else:
            return jsonify({'success': False, 'error': 'Falha ao criar backup'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/api/backup/<filename>/restore', methods=['POST'])
@admin_required
def restore_backup(filename):
    """Restaura backup do banco de dados"""
    try:
        from app.utils.backup import restore_database_backup
        
        success = restore_database_backup(filename)
        
        if success:
            return jsonify({'success': True, 'message': 'Backup restaurado com sucesso!'})
        else:
            return jsonify({'success': False, 'error': 'Falha ao restaurar backup'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@settings_bp.route('/api/backup/<filename>/delete', methods=['POST'])
@admin_required
def delete_backup(filename):
    """Exclui backup"""
    try:
        import os
        from app.config import BACKUP_FOLDER
        
        filepath = os.path.join(BACKUP_FOLDER, filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({'success': True, 'message': 'Backup excluído com sucesso!'})
        else:
            return jsonify({'success': False, 'error': 'Arquivo não encontrado'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500