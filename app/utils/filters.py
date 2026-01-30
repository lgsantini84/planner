# app/utils/filters.py
from datetime import datetime
import locale

def register_filters(app):
    """Registra filtros customizados no Jinja2"""
    
    @app.template_filter('date_ptbr')
    def date_ptbr_filter(date):
        """Formata data para formato brasileiro"""
        if date:
            return date.strftime('%d/%m/%Y %H:%M')
        return ''
    
    @app.template_filter('currency_br')
    def currency_br_filter(value):
        """Formata valor monetário para formato brasileiro"""
        try:
            locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
            return locale.currency(value, grouping=True)
        except:
            return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
    @app.template_global()
    def current_year():
        """Retorna o ano atual"""
        return datetime.now().year
    
    @app.template_global()
    def format_days_ago(date):
        """Formata data para "X dias atrás" """
        if not date:
            return "Nunca"
        
        delta = datetime.now() - date
        days = delta.days
        
        if days == 0:
            return "Hoje"
        elif days == 1:
            return "Ontem"
        elif days < 7:
            return f"{days} dias atrás"
        elif days < 30:
            weeks = days // 7
            return f"{weeks} semana{'s' if weeks > 1 else ''} atrás"
        elif days < 365:
            months = days // 30
            return f"{months} mês{'es' if months > 1 else ''} atrás"
        else:
            years = days // 365
            return f"{years} ano{'s' if years > 1 else ''} atrás"