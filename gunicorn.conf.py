import multiprocessing

# Configurações Gunicorn para produção

# Endereço e porta
bind = "0.0.0.0:5000"

# Número de workers
workers = multiprocessing.cpu_count() * 2 + 1

# Tipo de worker
worker_class = "sync"

# Timeouts
timeout = 120
keepalive = 5

# Logging
accesslog = "./logs/access.log"
errorlog = "./logs/error.log"
loglevel = "info"

# Configurações de segurança
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# Configurações de performance
max_requests = 1000
max_requests_jitter = 50

# Configurações de proxy
proxy_protocol = True
forwarded_allow_ips = "*"