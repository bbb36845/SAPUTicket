from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, current_user, login_required
import uuid
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.user import User, get_user_by_invitation_token

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Håndterer login-processen"""
    if current_user.is_authenticated:
        # Redirect to appropriate dashboard based on role
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == 'udlejer':
            return redirect(url_for('landlord.dashboard'))
        elif current_user.role == 'lejer':
            return redirect(url_for('tenant.dashboard'))
        elif current_user.role == 'håndværker':
            return redirect(url_for('craftsman.dashboard'))
        return redirect(url_for('common.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        if not username or not password:
            flash('Brugernavn og adgangskode er påkrævet', 'error')
            return render_template('auth/login.html')
        
        # Try to find user by username first, then by email
        user = User.get_by_username(username)
        if not user:
            user = User.get_by_email(username)
        
        if not user or not user.check_password(password):
            flash('Ugyldigt brugernavn eller adgangskode', 'error')
            return render_template('auth/login.html')
        
        # Check if user is active
        if not user.is_active:
            flash('Din konto er deaktiveret. Kontakt venligst administrator.', 'error')
            return render_template('auth/login.html')
        
        login_user(user, remember=remember)
        
        # Redirect to the appropriate dashboard based on role
        if user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif user.role == 'udlejer':
            return redirect(url_for('landlord.dashboard'))
        elif user.role == 'lejer':
            return redirect(url_for('tenant.dashboard'))
        elif user.role == 'håndværker':
            return redirect(url_for('craftsman.dashboard'))
        
        return redirect(url_for('common.index'))
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """Logger brugeren ud"""
    logout_user()
    flash('Du er nu logget ud', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/invitation/<token>', methods=['GET', 'POST'])
def accept_invitation(token):
    """Håndterer accept af invitation og oprettelse af konto"""
    # Tjek om token er gyldigt
    user = get_user_by_invitation_token(token)
    
    if not user:
        flash('Invitationen er ugyldig eller udløbet.', 'error')
        return redirect(url_for('auth.login'))
    
    # Map roles to display names
    role_displays = {
        'admin': 'Administrator',
        'udlejer': 'Udlejer',
        'lejer': 'Lejer',
        'håndværker': 'Håndværker'
    }
    
    role_display = role_displays.get(user.role, user.role)
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Valider input
        if not password or not confirm_password:
            flash('Venligst udfyld alle felter.', 'error')
            return render_template('auth/accept_invitation.html', token=token, email=user.email, role_display=role_display)
        
        if password != confirm_password:
            flash('Kodeordene stemmer ikke overens.', 'error')
            return render_template('auth/accept_invitation.html', token=token, email=user.email, role_display=role_display)
        
        # Opdater brugerens kodeord og fjern invitationstoken
        user.set_password(password)
        
        # Nulstil invitation token
        from app.db import get_db_connection
        conn = get_db_connection()
        conn.execute('''
            UPDATE users 
            SET invitation_token = NULL, invitation_expires_at = NULL, updated_at = ?
            WHERE id = ?
        ''', (datetime.now(), user.id))
        conn.commit()
        conn.close()
        
        # Log brugeren ind
        login_user(user)
        
        flash('Din konto er nu aktiveret. Velkommen til SAPUTicket!', 'success')
        
        # Omstyring baseret på brugerrolle
        if user.role == 'udlejer':
            return redirect(url_for('landlord.dashboard'))
        elif user.role == 'lejer':
            return redirect(url_for('tenant.dashboard'))
        elif user.role == 'håndværker':
            return redirect(url_for('craftsman.dashboard'))
        else:
            return redirect(url_for('common.index'))
    
    return render_template('auth/accept_invitation.html', token=token, email=user.email, role_display=role_display)

@auth_bp.route('/password/reset', methods=['GET', 'POST'])
def request_password_reset():
    """Håndterer anmodning om nulstilling af kodeord"""
    if current_user.is_authenticated:
        return redirect(url_for('common.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Venligst angiv din e-mailadresse.', 'error')
            return render_template('auth/request_password_reset.html')
        
        # Find bruger med den angivne e-mail
        from app.db import get_db_connection
        conn = get_db_connection()
        user_data = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if not user_data:
            # For sikkerhed: vis samme besked, selvom brugeren ikke findes
            flash('Hvis din e-mail er registreret i systemet, vil du modtage instruktioner til nulstilling af kodeord.', 'info')
            return redirect(url_for('auth.login'))
        
        user = User.from_dict(user_data)
        
        # Generer reset token
        reset_token = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(hours=24)
        
        # Gem token i databasen
        conn = get_db_connection()
        conn.execute('''
            UPDATE users 
            SET reset_token = ?, reset_token_expires_at = ?, updated_at = ?
            WHERE id = ?
        ''', (reset_token, expires_at, datetime.now(), user.id))
        conn.commit()
        conn.close()
        
        # Send e-mail med reset link (implementeres senere)
        # send_password_reset_email(user, reset_token)
        
        flash('Hvis din e-mail er registreret i systemet, vil du modtage instruktioner til nulstilling af kodeord.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/request_password_reset.html')

@auth_bp.route('/password/reset/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Håndterer nulstilling af kodeord med token"""
    if current_user.is_authenticated:
        return redirect(url_for('common.index'))
    
    # Find bruger med det angivne reset token
    from app.db import get_db_connection
    conn = get_db_connection()
    user_data = conn.execute('''
        SELECT * FROM users 
        WHERE reset_token = ? AND reset_token_expires_at > ?
    ''', (token, datetime.now())).fetchone()
    conn.close()
    
    if not user_data:
        flash('Reset-linket er ugyldigt eller udløbet.', 'error')
        return redirect(url_for('auth.login'))
    
    user = User.from_dict(user_data)
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Valider input
        if not password or not confirm_password:
            flash('Venligst udfyld alle felter.', 'error')
            return render_template('auth/reset_password.html', token=token)
        
        if password != confirm_password:
            flash('Kodeordene stemmer ikke overens.', 'error')
            return render_template('auth/reset_password.html', token=token)
        
        # Opdater brugerens kodeord og fjern reset token
        user.set_password(password)
        
        # Nulstil reset token
        conn = get_db_connection()
        conn.execute('''
            UPDATE users 
            SET reset_token = NULL, reset_token_expires_at = NULL, updated_at = ?
            WHERE id = ?
        ''', (datetime.now(), user.id))
        conn.commit()
        conn.close()
        
        flash('Dit kodeord er nulstillet. Du kan nu logge ind med dit nye kodeord.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html')

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Viser og lader brugeren redigere sin profil"""
    user = current_user
    
    # Map roles to display names
    role_displays = {
        'admin': 'Administrator',
        'udlejer': 'Udlejer',
        'lejer': 'Lejer',
        'håndværker': 'Håndværker'
    }
    
    # Add role_display attribute for template
    user.role_display = role_displays.get(user.role, user.role)
    
    if request.method == 'POST':
        # Process form data
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        
        # Validation
        if not all([first_name, last_name, email]):
            flash('Alle påkrævede felter skal udfyldes', 'error')
            return render_template('auth/profile.html', user=user)
        
        # Check if the email is already taken by another user
        existing_user = User.get_by_email(email)
        if existing_user and existing_user.id != user.id:
            flash('E-mail adressen er allerede i brug', 'error')
            return render_template('auth/profile.html', user=user)
        
        # Update user record
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.phone = phone
        user.updated_at = datetime.now()
        
        user.save()
        
        flash('Din profil er blevet opdateret', 'success')
        
        # Update user.role_display for the template
        user.role_display = role_displays.get(user.role, user.role)
        
        return render_template('auth/profile.html', user=user)
    
    return render_template('auth/profile.html', user=user)

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Lader brugeren ændre sit kodeord"""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([current_password, new_password, confirm_password]):
            flash('Alle påkrævede felter skal udfyldes', 'error')
            return render_template('auth/change_password.html')
        
        if not current_user.check_password(current_password):
            flash('Nuværende adgangskode er forkert', 'error')
            return render_template('auth/change_password.html')
        
        if new_password != confirm_password:
            flash('De nye adgangskoder stemmer ikke overens', 'error')
            return render_template('auth/change_password.html')
        
        if len(new_password) < 8:
            flash('Adgangskoden skal være mindst 8 tegn lang', 'error')
            return render_template('auth/change_password.html')
        
        # Update password
        current_user.set_password(new_password)
        current_user.updated_at = datetime.now()
        current_user.save()
        
        flash('Din adgangskode er blevet opdateret', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/change_password.html') 