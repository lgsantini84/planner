from datetime import datetime, timedelta
import json
import re
import hashlib
import secrets
import string
from typing import Dict, List, Any, Optional
import logging
from urllib.parse import urlparse, urlencode
import pytz

logger = logging.getLogger(__name__)

class DateTimeHelper:
    """Helper para manipulação de datas e horas"""
    
    @staticmethod
    def parse_datetime(datetime_str: str, timezone: str = 'UTC') -> Optional[datetime]:
        """Converte string ISO para datetime com timezone"""
        if not datetime_str:
            return None
        
        try:
            # Substituir 'Z' por '+00:00' para compatibilidade
            if datetime_str.endswith('Z'):
                datetime_str = datetime_str[:-1] + '+00:00'
            
            dt = datetime.fromisoformat(datetime_str)
            
            # Converter para timezone especificada
            tz = pytz.timezone(timezone)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=pytz.UTC)
            
            return dt.astimezone(tz)
        except Exception as e:
            logger.warning(f"Erro ao converter data {datetime_str}: {str(e)}")
            return None
    
    @staticmethod
    def format_datetime(dt: datetime, format_str: str = '%d/%m/%Y %H:%M', 
                       timezone: str = 'America/Sao_Paulo') -> str:
        """Formata datetime para string"""
        if not dt:
            return ''
        
        try:
            # Converter para timezone especificada
            tz = pytz.timezone(timezone)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=pytz.UTC)
            
            local_dt = dt.astimezone(tz)
            return local_dt.strftime(format_str)
        except Exception as e:
            logger.warning(f"Erro ao formatar data {dt}: {str(e)}")
            return str(dt)
    
    @staticmethod
    def humanize_delta(delta: timedelta) -> str:
        """Converte timedelta para formato humano"""
        if delta.days > 365:
            years = delta.days // 365
            return f"{years} ano{'s' if years > 1 else ''}"
        elif delta.days > 30:
            months = delta.days // 30
            return f"{months} mês{'es' if months > 1 else ''}"
        elif delta.days > 0:
            return f"{delta.days} dia{'s' if delta.days > 1 else ''}"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours} hora{'s' if hours > 1 else ''}"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes} minuto{'s' if minutes > 1 else ''}"
        else:
            return "agora"
    
    @staticmethod
    def time_ago(dt: datetime) -> str:
        """Retorna string 'há X tempo'"""
        if not dt:
            return ''
        
        now = datetime.now(pytz.UTC)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        
        delta = now - dt
        
        if delta.days < 0:
            return "no futuro"
        
        human_delta = DateTimeHelper.humanize_delta(delta)
        return f"há {human_delta}"
    
    @staticmethod
    def is_business_day(dt: datetime) -> bool:
        """Verifica se é dia útil (segunda a sexta)"""
        return dt.weekday() < 5  # 0 = segunda, 4 = sexta
    
    @staticmethod
    def add_business_days(start_date: datetime, days: int) -> datetime:
        """Adiciona dias úteis a uma data"""
        current_date = start_date
        added_days = 0
        
        while added_days < days:
            current_date += timedelta(days=1)
            if DateTimeHelper.is_business_day(current_date):
                added_days += 1
        
        return current_date

class StringHelper:
    """Helper para manipulação de strings"""
    
    @staticmethod
    def truncate(text: str, length: int = 100, suffix: str = '...') -> str:
        """Trunca texto com sufixo"""
        if not text:
            return ''
        
        if len(text) <= length:
            return text
        
        return text[:length - len(suffix)].rstrip() + suffix
    
    @staticmethod
    def slugify(text: str) -> str:
        """Converte texto para slug"""
        if not text:
            return ''
        
        # Converter para minúsculas
        text = text.lower()
        
        # Remover caracteres especiais
        text = re.sub(r'[^\w\s-]', '', text)
        
        # Substituir espaços por hífens
        text = re.sub(r'[-\s]+', '-', text)
        
        return text
    
    @staticmethod
    def extract_emails(text: str) -> List[str]:
        """Extrai emails de um texto"""
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        return re.findall(email_pattern, text)
    
    @staticmethod
    def extract_hashtags(text: str) -> List[str]:
        """Extrai hashtags de um texto"""
        hashtag_pattern = r'#(\w+)'
        return re.findall(hashtag_pattern, text)
    
    @staticmethod
    def generate_random_string(length: int = 8, 
                              include_digits: bool = True,
                              include_special: bool = False) -> str:
        """Gera string aleatória"""
        chars = string.ascii_letters
        if include_digits:
            chars += string.digits
        if include_special:
            chars += string.punctuation
        
        return ''.join(secrets.choice(chars) for _ in range(length))
    
    @staticmethod
    def mask_email(email: str) -> str:
        """Mascara email para exibição"""
        if not email or '@' not in email:
            return email
        
        local_part, domain = email.split('@')
        
        if len(local_part) <= 2:
            masked_local = local_part[0] + '*' * (len(local_part) - 1)
        else:
            masked_local = local_part[0] + '*' * (len(local_part) - 2) + local_part[-1]
        
        domain_parts = domain.split('.')
        if len(domain_parts) >= 2:
            masked_domain = domain_parts[0][0] + '*' * (len(domain_parts[0]) - 1)
            for part in domain_parts[1:]:
                masked_domain += '.' + part[0] + '*' * (len(part) - 1)
        else:
            masked_domain = domain[0] + '*' * (len(domain) - 1)
        
        return f"{masked_local}@{masked_domain}"

class SecurityHelper:
    """Helper para segurança"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash de senha usando SHA-256"""
        salt = secrets.token_hex(16)
        hash_obj = hashlib.sha256()
        hash_obj.update(f"{password}{salt}".encode('utf-8'))
        return f"{hash_obj.hexdigest()}:{salt}"
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """Verifica senha hash"""
        try:
            hash_value, salt = hashed_password.split(':')
            hash_obj = hashlib.sha256()
            hash_obj.update(f"{password}{salt}".encode('utf-8'))
            return hash_obj.hexdigest() == hash_value
        except:
            return False
    
    @staticmethod
    def generate_api_key() -> str:
        """Gera chave de API"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_session_token() -> str:
        """Gera token de sessão"""
        return secrets.token_urlsafe(64)
    
    @staticmethod
    def sanitize_input(input_str: str) -> str:
        """Sanitiza entrada do usuário"""
        if not input_str:
            return ''
        
        # Remover tags HTML
        input_str = re.sub(r'<[^>]*>', '', input_str)
        
        # Escapar caracteres especiais
        input_str = input_str.replace('\\', '\\\\')
        input_str = input_str.replace('\'', '\\\'')
        input_str = input_str.replace('\"', '\\\"')
        
        return input_str.strip()

class ValidationHelper:
    """Helper para validações"""
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Valida formato de email"""
        if not email:
            return False
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, email))
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Valida formato de URL"""
        if not url:
            return False
        
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    @staticmethod
    def is_valid_date(date_str: str, format_str: str = '%Y-%m-%d') -> bool:
        """Valida formato de data"""
        if not date_str:
            return False
        
        try:
            datetime.strptime(date_str, format_str)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def is_valid_json(json_str: str) -> bool:
        """Valida se string é JSON válido"""
        try:
            json.loads(json_str)
            return True
        except json.JSONDecodeError:
            return False

class FileHelper:
    """Helper para manipulação de arquivos"""
    
    @staticmethod
    def get_file_size(bytes_size: int) -> str:
        """Converte bytes para formato legível"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"
    
    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Obtém extensão do arquivo"""
        if not filename or '.' not in filename:
            return ''
        
        return filename.rsplit('.', 1)[1].lower()
    
    @staticmethod
    def is_allowed_file(filename: str, allowed_extensions: set) -> bool:
        """Verifica se arquivo tem extensão permitida"""
        if not filename:
            return False
        
        return '.' in filename and \
               FileHelper.get_file_extension(filename) in allowed_extensions
    
    @staticmethod
    def generate_unique_filename(original_filename: str) -> str:
        """Gera nome de arquivo único"""
        import uuid
        import os
        
        ext = FileHelper.get_file_extension(original_filename)
        unique_id = str(uuid.uuid4())
        
        if ext:
            return f"{unique_id}.{ext}"
        else:
            return unique_id

class ColorHelper:
    """Helper para manipulação de cores"""
    
    @staticmethod
    def hex_to_rgb(hex_color: str) -> tuple:
        """Converte cor HEX para RGB"""
        hex_color = hex_color.lstrip('#')
        
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])
        
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    @staticmethod
    def rgb_to_hex(rgb: tuple) -> str:
        """Converte cor RGB para HEX"""
        return '#{:02x}{:02x}{:02x}'.format(*rgb)
    
    @staticmethod
    def lighten_color(hex_color: str, amount: float = 0.1) -> str:
        """Clareia uma cor"""
        rgb = ColorHelper.hex_to_rgb(hex_color)
        rgb = tuple(min(255, int(c + (255 - c) * amount)) for c in rgb)
        return ColorHelper.rgb_to_hex(rgb)
    
    @staticmethod
    def darken_color(hex_color: str, amount: float = 0.1) -> str:
        """Escurece uma cor"""
        rgb = ColorHelper.hex_to_rgb(hex_color)
        rgb = tuple(max(0, int(c * (1 - amount))) for c in rgb)
        return ColorHelper.rgb_to_hex(rgb)
    
    @staticmethod
    def get_contrast_color(hex_color: str) -> str:
        """Retorna cor de contraste (preto ou branco)"""
        rgb = ColorHelper.hex_to_rgb(hex_color)
        
        # Fórmula de luminância
        luminance = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255
        
        return '#000000' if luminance > 0.5 else '#ffffff'
    
    @staticmethod
    def generate_color_palette(base_color: str, count: int = 5) -> List[str]:
        """Gera paleta de cores a partir de uma cor base"""
        import colorsys
        
        # Converter HEX para RGB
        rgb = ColorHelper.hex_to_rgb(base_color)
        
        # Converter RGB para HSL
        h, l, s = colorsys.rgb_to_hls(rgb[0]/255, rgb[1]/255, rgb[2]/255)
        
        palette = []
        for i in range(count):
            # Variar luminosidade
            new_l = max(0.1, min(0.9, l + (i - count/2) * 0.1))
            
            # Converter HSL para RGB
            new_rgb = colorsys.hls_to_rgb(h, new_l, s)
            new_rgb = tuple(int(c * 255) for c in new_rgb)
            
            palette.append(ColorHelper.rgb_to_hex(new_rgb))
        
        return palette

class URLHelper:
    """Helper para manipulação de URLs"""
    
    @staticmethod
    def add_query_params(url: str, params: Dict) -> str:
        """Adiciona parâmetros de query a uma URL"""
        if not params:
            return url
        
        # Parse URL
        parsed = urlparse(url)
        
        # Obter query atual
        query_dict = {}
        if parsed.query:
            query_dict = dict(x.split('=') for x in parsed.query.split('&'))
        
        # Adicionar novos parâmetros
        query_dict.update(params)
        
        # Reconstruir URL
        new_query = urlencode(query_dict)
        return parsed._replace(query=new_query).geturl()
    
    @staticmethod
    def remove_query_params(url: str, params_to_remove: List[str]) -> str:
        """Remove parâmetros de query de uma URL"""
        if not params_to_remove:
            return url
        
        # Parse URL
        parsed = urlparse(url)
        
        # Obter query atual
        if not parsed.query:
            return url
        
        query_dict = dict(x.split('=') for x in parsed.query.split('&'))
        
        # Remover parâmetros
        for param in params_to_remove:
            query_dict.pop(param, None)
        
        # Reconstruir URL
        if query_dict:
            new_query = urlencode(query_dict)
            return parsed._replace(query=new_query).geturl()
        else:
            return parsed._replace(query='').geturl()
    
    @staticmethod
    def get_domain(url: str) -> str:
        """Obtém domínio de uma URL"""
        parsed = urlparse(url)
        return parsed.netloc
    
    @staticmethod
    def is_safe_url(url: str, allowed_hosts: List[str] = None) -> bool:
        """Verifica se URL é segura (não é redirecionamento malicioso)"""
        if not url:
            return False
        
        # URL relativa é sempre segura
        if url.startswith('/'):
            return True
        
        # Verificar URL absoluta
        parsed = urlparse(url)
        
        if not parsed.netloc:
            return True
        
        if allowed_hosts:
            return parsed.netloc in allowed_hosts
        
        return False

class DataHelper:
    """Helper para manipulação de dados"""
    
    @staticmethod
    def flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
        """Achata dicionário aninhado"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            
            if isinstance(v, dict):
                items.extend(DataHelper.flatten_dict(v, new_key, sep).items())
            else:
                items.append((new_key, v))
        
        return dict(items)
    
    @staticmethod
    def nest_dict(flat_dict: Dict, sep: str = '.') -> Dict:
        """Aninha dicionário achatado"""
        result = {}
        
        for key, value in flat_dict.items():
            parts = key.split(sep)
            d = result
            
            for part in parts[:-1]:
                if part not in d:
                    d[part] = {}
                d = d[part]
            
            d[parts[-1]] = value
        
        return result
    
    @staticmethod
    def filter_dict(d: Dict, keys: List[str]) -> Dict:
        """Filtra dicionário mantendo apenas chaves especificadas"""
        return {k: v for k, v in d.items() if k in keys}
    
    @staticmethod
    def exclude_dict(d: Dict, keys: List[str]) -> Dict:
        """Filtra dicionário excluindo chaves especificadas"""
        return {k: v for k, v in d.items() if k not in keys}
    
    @staticmethod
    def deep_merge(dict1: Dict, dict2: Dict) -> Dict:
        """Merge profundo de dois dicionários"""
        result = dict1.copy()
        
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = DataHelper.deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result

class CacheHelper:
    """Helper para cache"""
    
    @staticmethod
    def generate_cache_key(prefix: str, *args, **kwargs) -> str:
        """Gera chave de cache baseada em argumentos"""
        import hashlib
        import pickle
        
        # Serializar argumentos
        data = pickle.dumps((args, sorted(kwargs.items())))
        
        # Gerar hash
        hash_obj = hashlib.md5(data)
        hash_digest = hash_obj.hexdigest()
        
        return f"{prefix}:{hash_digest}"
    
    @staticmethod
    def memoize(expire: int = 300):
        """Decorator para memoização"""
        import time
        from functools import wraps
        
        cache = {}
        
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Gerar chave de cache
                cache_key = CacheHelper.generate_cache_key(
                    func.__name__, *args, **kwargs
                )
                
                # Verificar cache
                if cache_key in cache:
                    cached_value, cached_time = cache[cache_key]
                    if time.time() - cached_time < expire:
                        return cached_value
                
                # Executar função
                result = func(*args, **kwargs)
                
                # Armazenar em cache
                cache[cache_key] = (result, time.time())
                
                # Limpar cache expirado
                current_time = time.time()
                expired_keys = [
                    key for key, (_, cached_time) in cache.items()
                    if current_time - cached_time > expire
                ]
                for key in expired_keys:
                    del cache[key]
                
                return result
            
            return wrapper
        return decorator

class ProgressHelper:
    """Helper para progresso"""
    
    @staticmethod
    def progress_bar(iteration: int, total: int, length: int = 50, 
                    fill: str = '█', empty: str = '░') -> str:
        """Gera barra de progresso"""
        percent = f"{100 * (iteration / float(total)):.1f}"
        filled_length = int(length * iteration // total)
        bar = fill * filled_length + empty * (length - filled_length)
        return f"[{bar}] {percent}%"
    
    @staticmethod
    def estimate_time_remaining(start_time: datetime, completed: int, 
                              total: int) -> timedelta:
        """Estima tempo restante"""
        if completed == 0:
            return timedelta.max
        
        elapsed = datetime.now() - start_time
        time_per_item = elapsed / completed
        remaining_items = total - completed
        
        return time_per_item * remaining_items

class ExportHelper:
    """Helper para exportação"""
    
    @staticmethod
    def dataframe_to_html(df, title: str = '', include_index: bool = False) -> str:
        """Converte DataFrame para HTML"""
        import pandas as pd
        
        html = f'<h3>{title}</h3>' if title else ''
        html += df.to_html(index=include_index, classes='table table-striped')
        
        # Adicionar estilos
        html = f"""
        <html>
        <head>
            <style>
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; font-weight: bold; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
            </style>
        </head>
        <body>
            {html}
        </body>
        </html>
        """
        
        return html
    
    @staticmethod
    def generate_csv(data: List[Dict], filename: str = 'export.csv') -> bytes:
        """Gera CSV a partir de lista de dicionários"""
        import csv
        from io import StringIO
        
        if not data:
            return b''
        
        # Obter cabeçalhos
        headers = list(data[0].keys())
        
        # Criar CSV
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
        
        return output.getvalue().encode('utf-8-sig')