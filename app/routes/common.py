from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, jsonify, abort
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
import os

from app.models.user import User
from app.models.ticket import Ticket
from app.models.unit import Unit
from app.models.property import Property

# Opret blueprint for common routes
common_bp = Blueprint('common', __name__)

# Forside
@common_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(get_dashboard_url())
    return render_template('landing/index.html')

# Om os
@common_bp.route('/about')
def about():
    return render_template('landing/about.html')

# Kontakt
@common_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
        
        # Her kunne man implementere en email-sender
        
        flash('Din besked er blevet sendt! Vi vender tilbage hurtigst muligt.', 'success')
        return redirect(url_for('common.contact'))
        
    return render_template('landing/contact.html')

# Profil
@common_bp.route('/profile')
@login_required
def profile():
    return render_template('profile/index.html', user=current_user)

# Rediger profil
@common_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        
        # Validering
        errors = []
        if not username:
            errors.append('Brugernavn er påkrævet')
        if not email:
            errors.append('Email er påkrævet')
            
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('profile/edit.html', user=current_user)
        
        # Tjek om email allerede er taget
        if email != current_user.email:
            existing_user = User.get_by_email(email)
            if existing_user and existing_user['id'] != current_user.id:
                flash('Email er allerede i brug', 'error')
                return render_template('profile/edit.html', user=current_user)
        
        # Opdater profil
        User.update(
            user_id=current_user.id,
            username=username,
            email=email
        )
        
        flash('Din profil er opdateret', 'success')
        return redirect(url_for('common.profile'))
        
    return render_template('profile/edit.html', user=current_user)

# Skift adgangskode
@common_bp.route('/profile/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validering
        errors = []
        if not current_password:
            errors.append('Nuværende adgangskode er påkrævet')
        if not new_password:
            errors.append('Ny adgangskode er påkrævet')
        if new_password != confirm_password:
            errors.append('Adgangskoderne matcher ikke')
        if len(new_password) < 6:
            errors.append('Adgangskoden skal være mindst 6 tegn')
            
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('profile/change_password.html')
        
        # Tjek at nuværende adgangskode er korrekt
        if not User.check_password(current_user.id, current_password):
            flash('Nuværende adgangskode er forkert', 'error')
            return render_template('profile/change_password.html')
        
        # Opdater adgangskode
        User.update_password(current_user.id, new_password)
        
        flash('Din adgangskode er opdateret', 'success')
        return redirect(url_for('common.profile'))
        
    return render_template('profile/change_password.html')

# Hjælpefunktion til at få den relevante dashboard URL
def get_dashboard_url():
    if not current_user.is_authenticated:
        return url_for('auth.login')
        
    if current_user.role == 'admin':
        return url_for('admin.dashboard')
    elif current_user.role == 'udlejer':
        return url_for('landlord.dashboard')
    elif current_user.role == 'lejer':
        return url_for('tenant.dashboard')
    elif current_user.role == 'craftsman':
        return url_for('craftsman.dashboard')
    else:
        return url_for('common.index')

# Vis billede
@common_bp.route('/image/<path:filename>')
def show_image(filename):
    # Sikkerhedskontrol kunne implementeres her
    return redirect(url_for('static', filename=f'uploads/{filename}'))

# 404 fejlhåndtering
@common_bp.app_errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

# 500 fejlhåndtering
@common_bp.app_errorhandler(500)
def server_error(e):
    return render_template('errors/500.html'), 500 