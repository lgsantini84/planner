import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
import logging
from jinja2 import Template
from app.models import db, EmailTemplate, SystemSetting

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        self.app = app
        self.smtp_server = app.config.get('MAIL_SERVER')
        self.smtp_port = app.config.get('MAIL_PORT')
        self.smtp_username = app.config.get('MAIL_USERNAME')
        self.smtp_password = app.config.get('MAIL_PASSWORD')
        self.use_tls = app.config.get('MAIL_USE_TLS', True)
        self.default_sender = app.config.get('MAIL_DEFAULT_SENDER')
    
    def send_email(self, to_emails, subject, body_html, body_text=None, attachments=None, cc=None, bcc=None):
        """Envia um email"""
        try:
            if not self.smtp_server or not self.smtp_username:
                logger.warning("Configuração de email não definida")
                return False
            
            # Criar mensagem
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.default_sender
            msg['To'] = ', '.join(to_emails) if isinstance(to_emails, list) else to_emails
            
            if cc:
                msg['Cc'] = ', '.join(cc) if isinstance(cc, list) else cc
            
            # Adicionar corpo
            if body_text:
                part1 = MIMEText(body_text, 'plain')
                msg.attach(part1)
            
            part2 = MIMEText(body_html, 'html')
            msg.attach(part2)
            
            # Adicionar anexos
            if attachments:
                for attachment in attachments:
                    with open(attachment['path'], 'rb') as f:
                        part = MIMEApplication(f.read(), Name=attachment['filename'])
                    part['Content-Disposition'] = f'attachment; filename="{attachment["filename"]}"'
                    msg.attach(part)
            
            # Enviar email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                
                recipients = to_emails
                if cc:
                    recipients.extend(cc)
                if bcc:
                    recipients.extend(bcc)
                
                server.send_message(msg)
            
            logger.info(f"Email enviado para {to_emails}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar email: {str(e)}")
            return False
    
    def send_task_notification(self, task, notification_type, recipients):
        """Envia notificação sobre uma tarefa"""
        try:
            template = self.get_template(f"task_{notification_type}")
            if not template:
                logger.warning(f"Template não encontrado para {notification_type}")
                return False
            
            # Renderizar template
            context = {
                'task': task,
                'task_title': task.title,
                'task_id': task.id,
                'due_date': task.due_date.strftime('%d/%m/%Y') if task.due_date else '',
                'planner': task.planner.title if task.planner else '',
                'assignees': self._get_task_assignees(task),
                'notification_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'app_url': self.app.config.get('APP_BASE_URL', '')
            }
            
            subject = self._render_template(template.subject, context)
            body_html = self._render_template(template.body_html, context)
            body_text = self._render_template(template.body, context)
            
            # Enviar email
            return self.send_email(
                to_emails=recipients,
                subject=subject,
                body_html=body_html,
                body_text=body_text
            )
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificação de tarefa: {str(e)}")
            return False
    
    def send_daily_digest(self, user, tasks_due, tasks_overdue, tasks_completed):
        """Envia resumo diário"""
        try:
            template = self.get_template("daily_digest")
            if not template:
                return False
            
            context = {
                'user': user,
                'tasks_due': tasks_due,
                'tasks_overdue': tasks_overdue,
                'tasks_completed': tasks_completed,
                'date': datetime.now().strftime('%d/%m/%Y'),
                'total_tasks': len(tasks_due) + len(tasks_overdue) + len(tasks_completed),
                'app_url': self.app.config.get('APP_BASE_URL', '')
            }
            
            subject = self._render_template(template.subject, context)
            body_html = self._render_template(template.body_html, context)
            
            return self.send_email(
                to_emails=[user.email],
                subject=subject,
                body_html=body_html
            )
            
        except Exception as e:
            logger.error(f"Erro ao enviar resumo diário: {str(e)}")
            return False
    
    def send_report_email(self, report, report_path, recipients):
        """Envia relatório por email"""
        try:
            template = self.get_template("report_delivery")
            if not template:
                template = EmailTemplate(
                    subject="Relatório: {{report_name}}",
                    body_html="""
                    <h2>Relatório {{report_name}}</h2>
                    <p>O relatório foi gerado em {{generation_date}}.</p>
                    <p>Total de registros: {{record_count}}</p>
                    <p><a href="{{app_url}}">Acessar o sistema</a></p>
                    """
                )
            
            context = {
                'report': report,
                'report_name': report.name,
                'generation_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'record_count': report.report_runs[-1].records_processed if report.report_runs else 0,
                'app_url': self.app.config.get('APP_BASE_URL', '')
            }
            
            subject = self._render_template(template.subject, context)
            body_html = self._render_template(template.body_html, context)
            
            attachments = [{
                'filename': f"{report.name}.xlsx",
                'path': report_path
            }]
            
            return self.send_email(
                to_emails=recipients,
                subject=subject,
                body_html=body_html,
                attachments=attachments
            )
            
        except Exception as e:
            logger.error(f"Erro ao enviar relatório por email: {str(e)}")
            return False
    
    def get_template(self, template_name):
        """Obtém template de email"""
        return EmailTemplate.query.filter_by(name=template_name, is_active=True).first()
    
    def _render_template(self, template_string, context):
        """Renderiza template com contexto"""
        if not template_string:
            return ""
        
        template = Template(template_string)
        return template.render(**context)
    
    def _get_task_assignees(self, task):
        """Obtém lista de responsáveis pela tarefa"""
        assignments = task.get_assignments()
        assignees = []
        
        for user_id, assignment in assignments.items():
            assignees.append({
                'name': assignment.get('userDisplayName', ''),
                'email': assignment.get('userEmail', '')
            })
        
        return assignees