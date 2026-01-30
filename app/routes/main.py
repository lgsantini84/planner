# app/routes/main.py
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    # Redirecionar para a página de login em vez de tentar renderizar um template que não existe
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Para teste, vamos criar um template simples
    return render_template('dashboard/index.html')

@main_bp.route('/about')
def about():
    return "<h1>Sobre o Planner Dashboard</h1><p>Esta é uma aplicação para gerenciamento de tarefas do Microsoft Planner.</p>"

@main_bp.route('/help')
def help():
    return "<h1>Ajuda</h1><p>Página de ajuda em construção.</p>"