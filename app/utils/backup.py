import os
import shutil
import subprocess
from datetime import datetime
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class BackupManager:
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        self.app = app
        self.backup_folder = app.config.get('BACKUP_FOLDER', 'backups')
        self.database_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        
        # Criar pasta de backups se não existir
        os.makedirs(self.backup_folder, exist_ok=True)
        os.makedirs(os.path.join(self.backup_folder, 'database'), exist_ok=True)
        os.makedirs(os.path.join(self.backup_folder, 'system'), exist_ok=True)
    
    def create_database_backup(self) -> Optional[str]:
        """Cria backup do banco de dados"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"backup_{timestamp}.sql"
            backup_path = os.path.join(self.backup_folder, 'database', backup_filename)
            
            if self.database_url.startswith('postgresql'):
                # Backup PostgreSQL usando pg_dump
                import urllib.parse
                
                parsed = urllib.parse.urlparse(self.database_url)
                db_name = parsed.path[1:]  # Remove a barra inicial
                
                command = [
                    'pg_dump',
                    '-h', parsed.hostname or 'localhost',
                    '-p', str(parsed.port or 5432),
                    '-U', parsed.username or 'postgres',
                    '-d', db_name,
                    '-f', backup_path
                ]
                
                # Configurar variável de ambiente para senha
                env = os.environ.copy()
                env['PGPASSWORD'] = parsed.password or ''
                
                subprocess.run(command, env=env, check=True)
                
            elif self.database_url.startswith('sqlite'):
                # Backup SQLite copiando o arquivo
                db_path = self.database_url.replace('sqlite:///', '')
                shutil.copy2(db_path, backup_path)
            
            else:
                logger.error(f"Tipo de banco não suportado para backup: {self.database_url}")
                return None
            
            logger.info(f"Backup criado: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Erro ao criar backup: {str(e)}")
            return None
    
    def restore_database_backup(self, backup_filename: str) -> bool:
        """Restaura backup do banco de dados"""
        try:
            backup_path = os.path.join(self.backup_folder, 'database', backup_filename)
            
            if not os.path.exists(backup_path):
                logger.error(f"Arquivo de backup não encontrado: {backup_path}")
                return False
            
            if self.database_url.startswith('postgresql'):
                # Restaurar PostgreSQL usando psql
                import urllib.parse
                
                parsed = urllib.parse.urlparse(self.database_url)
                db_name = parsed.path[1:]  # Remove a barra inicial
                
                # Primeiro, dropar e recriar o banco
                drop_command = [
                    'psql',
                    '-h', parsed.hostname or 'localhost',
                    '-p', str(parsed.port or 5432),
                    '-U', parsed.username or 'postgres',
                    '-c', f'DROP DATABASE IF EXISTS {db_name};'
                ]
                
                create_command = [
                    'psql',
                    '-h', parsed.hostname or 'localhost',
                    '-p', str(parsed.port or 5432),
                    '-U', parsed.username or 'postgres',
                    '-c', f'CREATE DATABASE {db_name};'
                ]
                
                restore_command = [
                    'psql',
                    '-h', parsed.hostname or 'localhost',
                    '-p', str(parsed.port or 5432),
                    '-U', parsed.username or 'postgres',
                    '-d', db_name,
                    '-f', backup_path
                ]
                
                # Configurar variável de ambiente para senha
                env = os.environ.copy()
                env['PGPASSWORD'] = parsed.password or ''
                
                subprocess.run(drop_command, env=env, check=True)
                subprocess.run(create_command, env=env, check=True)
                subprocess.run(restore_command, env=env, check=True)
            
            elif self.database_url.startswith('sqlite'):
                # Restaurar SQLite copiando o arquivo
                db_path = self.database_url.replace('sqlite:///', '')
                shutil.copy2(backup_path, db_path)
            
            else:
                logger.error(f"Tipo de banco não suportado para restauração: {self.database_url}")
                return False
            
            logger.info(f"Backup restaurado: {backup_filename}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao restaurar backup: {str(e)}")
            return False
    
    def create_system_backup(self) -> Optional[str]:
        """Cria backup do sistema (configurações, templates, etc.)"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"system_backup_{timestamp}.tar.gz"
            backup_path = os.path.join(self.backup_folder, 'system', backup_filename)
            
            # Pastas para backup
            folders_to_backup = [
                'config.py',
                '.env',
                'templates',
                'static',
                'uploads'
            ]
            
            # Criar arquivo tar.gz
            import tarfile
            
            with tarfile.open(backup_path, 'w:gz') as tar:
                for folder in folders_to_backup:
                    if os.path.exists(folder):
                        tar.add(folder)
            
            logger.info(f"Backup do sistema criado: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Erro ao criar backup do sistema: {str(e)}")
            return None
    
    def list_backups(self, backup_type: str = 'database') -> list:
        """Lista backups disponíveis"""
        backup_dir = os.path.join(self.backup_folder, backup_type)
        
        if not os.path.exists(backup_dir):
            return []
        
        backups = []
        for filename in os.listdir(backup_dir):
            filepath = os.path.join(backup_dir, filename)
            stats = os.stat(filepath)
            
            backups.append({
                'filename': filename,
                'path': filepath,
                'size': stats.st_size,
                'created': datetime.fromtimestamp(stats.st_ctime),
                'modified': datetime.fromtimestamp(stats.st_mtime)
            })
        
        # Ordenar por data de criação (mais recente primeiro)
        backups.sort(key=lambda x: x['created'], reverse=True)
        return backups
    
    def cleanup_old_backups(self, days_to_keep: int = 30) -> int:
        """Remove backups antigos"""
        try:
            cutoff_date = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - datetime.timedelta(days=days_to_keep)
            
            backups_removed = 0
            
            for backup_type in ['database', 'system']:
                backup_dir = os.path.join(self.backup_folder, backup_type)
                
                if not os.path.exists(backup_dir):
                    continue
                
                for filename in os.listdir(backup_dir):
                    filepath = os.path.join(backup_dir, filename)
                    stats = os.stat(filepath)
                    created_date = datetime.fromtimestamp(stats.st_ctime)
                    
                    if created_date < cutoff_date:
                        os.remove(filepath)
                        backups_removed += 1
                        logger.info(f"Backup antigo removido: {filename}")
            
            return backups_removed
            
        except Exception as e:
            logger.error(f"Erro ao limpar backups antigos: {str(e)}")
            return 0