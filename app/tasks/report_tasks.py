from celery import shared_task
import logging
from datetime import datetime, timedelta
import os

from app import db
from app.models import Report, ReportRun, User
from app.services.report_service import ReportService
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

@shared_task
def run_report_task(report_id: int, run_id: int, user_id: int):
    """Executa um relatório em background"""
    try:
        report = Report.query.get(report_id)
        report_run = ReportRun.query.get(run_id)
        user = User.query.get(user_id)
        
        if not report or not report_run or not user:
            report_run.status = 'failed'
            report_run.error_message = 'Dados não encontrados'
            db.session.commit()
            return False
        
        # Atualizar status
        report_run.status = 'running'
        db.session.commit()
        
        start_time = datetime.utcnow()
        
        try:
            # Gerar relatório
            report_service = ReportService(user)
            
            if report.report_type == 'tasks':
                report_data = report_service.generate_task_report(
                    report.get_filters()
                )
            elif report.report_type == 'performance':
                report_data = report_service.generate_performance_report(
                    report.get_filters().get('start_date'),
                    report.get_filters().get('end_date')
                )
            else:
                raise ValueError(f"Tipo de relatório não suportado: {report.report_type}")
            
            # Exportar para o formato solicitado
            if report.report_format == 'excel':
                output = report_service.export_to_excel(
                    report_data, 
                    f"{report.name}.xlsx"
                )
            elif report.report_format == 'csv':
                # Implementar exportação CSV
                pass
            elif report.report_format == 'pdf':
                # Implementar exportação PDF
                pass
            else:
                raise ValueError(f"Formato não suportado: {report.report_format}")
            
            # Salvar arquivo
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{report.name}_{timestamp}.{report.report_format}"
            filepath = os.path.join('reports', 'generated', filename)
            
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'wb') as f:
                f.write(output.getvalue())
            
            # Atualizar registro de execução
            report_run.status = 'completed'
            report_run.completed_at = datetime.utcnow()
            report_run.duration = (report_run.completed_at - start_time).total_seconds()
            report_run.result_path = filepath
            report_run.records_processed = report_data.get('total_tasks', 0)
            report_run.file_size = os.path.getsize(filepath)
            
            report.last_run = report_run.completed_at
            
            # Enviar email se houver destinatários
            recipients = report.get_recipients()
            if recipients and report.is_active:
                email_service = EmailService()
                email_service.send_report_email(report, filepath, recipients)
            
            db.session.commit()
            
            logger.info(f"Relatório {report_id} executado com sucesso: {filename}")
            return True
            
        except Exception as e:
            report_run.status = 'failed'
            report_run.error_message = str(e)
            report_run.completed_at = datetime.utcnow()
            db.session.commit()
            
            logger.error(f"Erro ao executar relatório {report_id}: {str(e)}")
            return False
        
    except Exception as e:
        logger.error(f"Erro na tarefa de relatório: {str(e)}")
        return False

@shared_task
def process_scheduled_reports():
    """Processa relatórios agendados"""
    try:
        now = datetime.utcnow()
        
        # Buscar relatórios agendados para execução
        scheduled_reports = Report.query.filter(
            Report.is_active == True,
            Report.schedule != 'none',
            or_(
                Report.next_run <= now,
                Report.next_run.is_(None)
            )
        ).all()
        
        processed = 0
        for report in scheduled_reports:
            try:
                # Criar registro de execução
                report_run = ReportRun(
                    report_id=report.id,
                    status='pending',
                    started_at=datetime.utcnow()
                )
                db.session.add(report_run)
                db.session.commit()
                
                # Executar relatório em background
                run_report_task.delay(report.id, report_run.id, report.user_id)
                
                # Calcular próxima execução
                report.next_run = calculate_next_run(report.schedule)
                db.session.commit()
                
                processed += 1
                
            except Exception as e:
                logger.error(f"Erro ao agendar relatório {report.id}: {str(e)}")
        
        logger.info(f"Relatórios agendados processados: {processed}")
        return processed
        
    except Exception as e:
        logger.error(f"Erro ao processar relatórios agendados: {str(e)}")
        return 0

def calculate_next_run(schedule: str) -> datetime:
    """Calcula próxima execução baseada no schedule"""
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

@shared_task
def cleanup_old_reports(days: int = 90):
    """Limpa relatórios antigos"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Buscar relatórios antigos
        old_reports = ReportRun.query.filter(
            ReportRun.completed_at < cutoff_date
        ).all()
        
        deleted = 0
        for report_run in old_reports:
            try:
                # Excluir arquivo se existir
                if report_run.result_path and os.path.exists(report_run.result_path):
                    os.remove(report_run.result_path)
                
                # Excluir registro do banco
                db.session.delete(report_run)
                deleted += 1
                
            except Exception as e:
                logger.error(f"Erro ao excluir relatório {report_run.id}: {str(e)}")
        
        db.session.commit()
        
        logger.info(f"Relatórios antigos excluídos: {deleted}")
        return deleted
        
    except Exception as e:
        logger.error(f"Erro ao limpar relatórios antigos: {str(e)}")
        return 0