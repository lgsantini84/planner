from functools import wraps
from flask import request, jsonify, current_app
from flask_login import current_user
from datetime import datetime, timedelta
import time
from functools import lru_cache

def token_required(f):
    """Decorator para verificar token de acesso"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Token de acesso necessário'}), 401
        
        # Verificar se token está expirado
        if current_user.token_expires and current_user.token_expires < datetime.utcnow():
            return jsonify({'success': False, 'error': 'Token expirado'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator para verificar se usuário é admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Acesso não autorizado'}), 401
        
        if not current_user.is_admin:
            return jsonify({'success': False, 'error': 'Acesso restrito a administradores'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    """Decorator para verificar papel específico"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'success': False, 'error': 'Acesso não autorizado'}), 401
            
            # Implementar lógica de roles se necessário
            if role == 'admin' and not current_user.is_admin:
                return jsonify({'success': False, 'error': 'Acesso restrito a administradores'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def rate_limit(requests_per_minute=60, window_seconds=60):
    """Decorator para rate limiting"""
    def decorator(f):
        # Cache para armazenar contagens de requisições
        request_counts = {}
        
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Usar IP do cliente como chave
            client_ip = request.remote_addr
            
            # Obter timestamp atual
            now = time.time()
            window_start = now - window_seconds
            
            # Limpar requisições antigas
            if client_ip in request_counts:
                request_counts[client_ip] = [
                    timestamp for timestamp in request_counts[client_ip]
                    if timestamp > window_start
                ]
            else:
                request_counts[client_ip] = []
            
            # Verificar se excedeu o limite
            if len(request_counts[client_ip]) >= requests_per_minute:
                return jsonify({
                    'success': False,
                    'error': 'Limite de requisições excedido',
                    'retry_after': window_seconds
                }), 429
            
            # Adicionar requisição atual
            request_counts[client_ip].append(now)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def cache_response(timeout=300):
    """Decorator para cache de respostas"""
    def decorator(f):
        cache_store = {}
        
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Gerar chave de cache baseada na URL e parâmetros
            cache_key = f"{request.path}?{request.query_string.decode()}"
            
            # Verificar se há cache válido
            if cache_key in cache_store:
                cached_data, cached_time = cache_store[cache_key]
                if time.time() - cached_time < timeout:
                    return cached_data
            
            # Executar função e armazenar resultado
            result = f(*args, **kwargs)
            cache_store[cache_key] = (result, time.time())
            
            # Limpar cache antigo
            current_time = time.time()
            expired_keys = [
                key for key, (_, cached_time) in cache_store.items()
                if current_time - cached_time > timeout
            ]
            for key in expired_keys:
                del cache_store[key]
            
            return result
        return decorated_function
    return decorator

def validate_json(schema=None):
    """Decorator para validar JSON de entrada"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({'success': False, 'error': 'Content-Type deve ser application/json'}), 415
            
            data = request.get_json()
            
            if schema:
                # Implementar validação com schema (ex: marshmallow, pydantic)
                errors = schema.validate(data)
                if errors:
                    return jsonify({
                        'success': False,
                        'error': 'Dados inválidos',
                        'details': errors
                    }), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def track_activity(activity_type):
    """Decorator para rastrear atividades do usuário"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from app.models import ActivityLog
            
            # Executar função
            result = f(*args, **kwargs)
            
            # Registrar atividade se usuário estiver autenticado
            if current_user.is_authenticated:
                activity = ActivityLog(
                    user_id=current_user.id,
                    activity_type=activity_type,
                    description=f'{activity_type} via {request.path}',
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string
                )
                
                from app import db
                db.session.add(activity)
                db.session.commit()
            
            return result
        return decorated_function
    return decorator

def handle_exceptions(f):
    """Decorator para tratamento global de exceções"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            current_app.logger.error(f"Erro em {f.__name__}: {str(e)}", exc_info=True)
            
            # Verificar tipo de erro
            if isinstance(e, ValueError):
                return jsonify({'success': False, 'error': str(e)}), 400
            elif isinstance(e, PermissionError):
                return jsonify({'success': False, 'error': 'Acesso não autorizado'}), 403
            elif isinstance(e, FileNotFoundError):
                return jsonify({'success': False, 'error': 'Arquivo não encontrado'}), 404
            else:
                return jsonify({'success': False, 'error': 'Erro interno do servidor'}), 500
    
    return decorated_function

def require_feature(feature_name):
    """Decorator para verificar se feature está habilitada"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            feature_enabled = current_app.config.get(f'ENABLE_{feature_name.upper()}', False)
            
            if not feature_enabled:
                return jsonify({
                    'success': False,
                    'error': f'Feature {feature_name} não está habilitada'
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def async_task(timeout=30):
    """Decorator para executar tarefas assíncronas"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from app.tasks import execute_async_task
            
            # Executar tarefa em background
            task_id = execute_async_task.delay(f.__name__, args, kwargs)
            
            return jsonify({
                'success': True,
                'message': 'Tarefa iniciada em background',
                'task_id': task_id
            })
        return decorated_function
    return decorator

def compress_response(f):
    """Decorator para compressão de resposta"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import after_this_request
        
        @after_this_request
        def compress_response(response):
            # Implementar compressão gzip/deflate
            accept_encoding = request.headers.get('Accept-Encoding', '')
            
            if 'gzip' in accept_encoding:
                from io import BytesIO
                import gzip
                
                content = BytesIO()
                with gzip.GzipFile(fileobj=content, mode='wb') as gzip_file:
                    gzip_file.write(response.get_data())
                
                response.set_data(content.getvalue())
                response.headers['Content-Encoding'] = 'gzip'
                response.headers['Vary'] = 'Accept-Encoding'
                response.headers['Content-Length'] = len(response.get_data())
            
            return response
        
        return f(*args, **kwargs)
    return decorated_function

def paginate(default_per_page=50, max_per_page=100):
    """Decorator para paginação automática"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Obter parâmetros de paginação
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', default_per_page, type=int)
            
            # Limitar per_page
            per_page = min(per_page, max_per_page)
            
            # Adicionar parâmetros ao contexto
            request.page = page
            request.per_page = per_page
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def cors_headers(origins=None, methods=None, headers=None):
    """Decorator para headers CORS"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import make_response
            
            response = make_response(f(*args, **kwargs))
            
            # Configurar headers CORS
            if origins:
                response.headers['Access-Control-Allow-Origin'] = origins
            else:
                response.headers['Access-Control-Allow-Origin'] = '*'
            
            if methods:
                response.headers['Access-Control-Allow-Methods'] = methods
            else:
                response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            
            if headers:
                response.headers['Access-Control-Allow-Headers'] = headers
            else:
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Max-Age'] = '86400'
            
            return response
        return decorated_function
    return decorator

def maintenance_mode(f):
    """Decorator para modo de manutenção"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from app.models import SystemSetting
        
        # Verificar se modo de manutenção está ativo
        maintenance = SystemSetting.query.filter_by(key='maintenance_mode').first()
        
        if maintenance and maintenance.get_value() == True:
            return jsonify({
                'success': False,
                'error': 'Sistema em manutenção. Tente novamente mais tarde.',
                'maintenance_mode': True
            }), 503
        
        return f(*args, **kwargs)
    return decorated_function

def audit_log(action):
    """Decorator para logs de auditoria detalhados"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from app.models import AuditLog
            import json
            
            # Capturar dados da requisição
            request_data = {
                'method': request.method,
                'path': request.path,
                'query_params': dict(request.args),
                'headers': dict(request.headers),
                'remote_addr': request.remote_addr
            }
            
            if request.is_json:
                request_data['json_body'] = request.get_json()
            elif request.form:
                request_data['form_data'] = dict(request.form)
            
            # Executar função
            start_time = time.time()
            try:
                result = f(*args, **kwargs)
                success = True
                error = None
            except Exception as e:
                result = None
                success = False
                error = str(e)
                raise
            finally:
                end_time = time.time()
                duration = end_time - start_time
                
                # Registrar log de auditoria
                if current_user.is_authenticated:
                    audit_log_entry = AuditLog(
                        user_id=current_user.id,
                        action=action,
                        request_data=json.dumps(request_data),
                        response_status=200 if success else 500,
                        error_message=error,
                        duration=duration,
                        ip_address=request.remote_addr,
                        user_agent=request.user_agent.string
                    )
                    
                    from app import db
                    db.session.add(audit_log_entry)
                    db.session.commit()
            
            return result
        return decorated_function
    return decorator