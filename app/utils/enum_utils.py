from app.models import TaskStatus, TaskPriority

def string_to_task_status(status_str: str) -> TaskStatus:
    """Converte string para TaskStatus enum"""
    status_map = {
        'not_started': TaskStatus.NOT_STARTED,
        'in_progress': TaskStatus.IN_PROGRESS,
        'completed': TaskStatus.COMPLETED,
        'overdue': TaskStatus.OVERDUE,
        'blocked': TaskStatus.BLOCKED,
        'not_started': TaskStatus.NOT_STARTED,
        'in_progress': TaskStatus.IN_PROGRESS,
        'completed': TaskStatus.COMPLETED,
        'overdue': TaskStatus.OVERDUE,
        'blocked': TaskStatus.BLOCKED,
    }
    
    # Tentar conversão direta primeiro
    try:
        return TaskStatus(status_str)
    except ValueError:
        # Tentar mapeamento
        status_str_lower = status_str.lower()
        if status_str_lower in status_map:
            return status_map[status_str_lower]
        else:
            # Valor padrão
            return TaskStatus.NOT_STARTED

def string_to_task_priority(priority_str: str) -> TaskPriority:
    """Converte string para TaskPriority enum"""
    priority_map = {
        '0': TaskPriority.LOW,
        '1': TaskPriority.MEDIUM,
        '2': TaskPriority.HIGH,
        '3': TaskPriority.URGENT,
        'low': TaskPriority.LOW,
        'medium': TaskPriority.MEDIUM,
        'high': TaskPriority.HIGH,
        'urgent': TaskPriority.URGENT,
    }
    
    # Se for número, converter para string
    if isinstance(priority_str, (int, float)):
        priority_str = str(int(priority_str))
    
    # Tentar conversão direta primeiro
    try:
        if priority_str.isdigit():
            return TaskPriority(int(priority_str))
    except (ValueError, AttributeError):
        pass
    
    # Tentar mapeamento
    priority_str_lower = str(priority_str).lower()
    if priority_str_lower in priority_map:
        return priority_map[priority_str_lower]
    else:
        # Valor padrão
        return TaskPriority.MEDIUM