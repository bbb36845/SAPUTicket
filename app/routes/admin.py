from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import csv
import io

from app.models.user import User
from app.models.ticket import Ticket
from app.models.unit import Unit
from app.models.property import Property
from app.services.file_service import allowed_file, save_uploaded_file

# Opret blueprint for admin routes
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Decorator for at sikre at kun administratorer har adgang
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Du har ikke adgang til denne side. Log ind som administrator for at fortsætte.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin dashboard
@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    # Hent statistik for tickets
    all_tickets = Ticket.get_all()
    
    total_tickets = len(all_tickets)
    open_tickets = sum(1 for ticket in all_tickets if ticket['status'] == 'open')
    in_progress_tickets = sum(1 for ticket in all_tickets if ticket['status'] == 'in_progress')
    completed_tickets = sum(1 for ticket in all_tickets if ticket['status'] == 'completed')
    on_hold_tickets = sum(1 for ticket in all_tickets if ticket['status'] == 'on_hold')
    
    # Hent statistik for brugere
    users = User.get_all()
    
    total_users = len(users)
    admin_users = sum(1 for user in users if user['role'] == 'admin')
    landlord_users = sum(1 for user in users if user['role'] == 'udlejer')
    tenant_users = sum(1 for user in users if user['role'] == 'lejer')
    craftsman_users = sum(1 for user in users if user['role'] == 'craftsman')
    
    # Hent statistik for ejendomme og lejemål
    properties = Property.get_all()
    units = Unit.get_all()
    
    total_properties = len(properties)
    total_units = len(units)
    
    # Hent de seneste 10 tickets
    recent_tickets = sorted(all_tickets, key=lambda x: x.get('updated_at', ''), reverse=True)[:10]
    
    # Hent statistik for ejendomme, aktivitet, osv.
    return render_template('admin/dashboard.html',
                           user=current_user,
                           ticket_stats={
                               'total': total_tickets,
                               'open': open_tickets,
                               'in_progress': in_progress_tickets,
                               'completed': completed_tickets,
                               'on_hold': on_hold_tickets
                           },
                           user_stats={
                               'total': total_users,
                               'admin': admin_users,
                               'landlord': landlord_users,
                               'tenant': tenant_users,
                               'craftsman': craftsman_users
                           },
                           property_stats={
                               'total_properties': total_properties,
                               'total_units': total_units
                           },
                           recent_tickets=recent_tickets)

# Brugerstyring
@admin_bp.route('/users')
@login_required
@admin_required
def users():
    # Hent alle brugere
    users = User.get_all()
    
    return render_template('admin/users.html', users=users)

# Rediger bruger
@admin_bp.route('/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    # Hent bruger
    user = User.get_by_id(user_id)
    
    if not user:
        flash('Bruger ikke fundet', 'error')
        return redirect(url_for('admin.users'))
    
    if request.method == 'POST':
        # Hent formdata
        username = request.form.get('username')
        email = request.form.get('email')
        role = request.form.get('role')
        active = request.form.get('active') == 'on'
        
        # Validering
        errors = []
        if not username:
            errors.append('Brugernavn er påkrævet')
        if not email:
            errors.append('Email er påkrævet')
        if not role:
            errors.append('Rolle er påkrævet')
            
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('admin/edit_user.html', user=user)
        
        # Opdater bruger
        User.update(
            user_id=user_id,
            username=username,
            email=email,
            role=role,
            active=active
        )
        
        flash('Bruger er opdateret med succes!', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/edit_user.html', user=user)

# Nulstil adgangskode
@admin_bp.route('/user/<int:user_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def reset_password(user_id):
    # Hent bruger
    user = User.get_by_id(user_id)
    
    if not user:
        flash('Bruger ikke fundet', 'error')
        return redirect(url_for('admin.users'))
    
    # Generer ny adgangskode
    new_password = User.generate_password()
    
    # Opdater brugerens adgangskode
    User.update_password(user_id, new_password)
    
    flash(f'Adgangskode nulstillet for {user["username"]}. Ny adgangskode: {new_password}', 'success')
    return redirect(url_for('admin.edit_user', user_id=user_id))

# Slet bruger
@admin_bp.route('/user/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    # Hent bruger
    user = User.get_by_id(user_id)
    
    if not user:
        flash('Bruger ikke fundet', 'error')
        return redirect(url_for('admin.users'))
    
    # Kontroller at brugeren ikke er den aktuelle bruger
    if user_id == current_user.id:
        flash('Du kan ikke slette din egen konto', 'error')
        return redirect(url_for('admin.users'))
    
    # Slet bruger
    User.delete(user_id)
    
    flash('Bruger er slettet med succes!', 'success')
    return redirect(url_for('admin.users'))

# Ejendomsstyring
@admin_bp.route('/properties')
@login_required
@admin_required
def properties():
    # Hent alle ejendomme
    properties = Property.get_all()
    
    return render_template('admin/properties.html', properties=properties)

# Opret ejendom
@admin_bp.route('/property/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_property():
    if request.method == 'POST':
        # Hent formdata
        name = request.form.get('name')
        address = request.form.get('address')
        landlord_id = request.form.get('landlord_id')
        
        # Validering
        errors = []
        if not name:
            errors.append('Navn er påkrævet')
        if not address:
            errors.append('Adresse er påkrævet')
        if not landlord_id:
            errors.append('Udlejer er påkrævet')
            
        if errors:
            for error in errors:
                flash(error, 'error')
            # Hent udlejere til dropdown
            landlords = User.get_by_role('udlejer')
            return render_template('admin/create_property.html', landlords=landlords)
        
        # Opret ejendom
        property_id = Property.create(
            name=name,
            address=address,
            landlord_id=landlord_id
        )
        
        # Håndter filupload hvis der er nogen
        if 'image' in request.files:
            image = request.files['image']
            if image and image.filename != '' and allowed_file(image.filename):
                filename = save_uploaded_file(image, f'property_{property_id}')
                if filename:
                    Property.update_image(property_id, filename)
        
        flash('Ejendom er oprettet med succes!', 'success')
        return redirect(url_for('admin.properties'))
    
    # Hent udlejere til dropdown
    landlords = User.get_by_role('udlejer')
    return render_template('admin/create_property.html', landlords=landlords)

# Rediger ejendom
@admin_bp.route('/property/<int:property_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_property(property_id):
    # Hent ejendom
    property_info = Property.get_by_id(property_id)
    
    if not property_info:
        flash('Ejendom ikke fundet', 'error')
        return redirect(url_for('admin.properties'))
    
    if request.method == 'POST':
        # Hent formdata
        name = request.form.get('name')
        address = request.form.get('address')
        landlord_id = request.form.get('landlord_id')
        
        # Validering
        errors = []
        if not name:
            errors.append('Navn er påkrævet')
        if not address:
            errors.append('Adresse er påkrævet')
        if not landlord_id:
            errors.append('Udlejer er påkrævet')
            
        if errors:
            for error in errors:
                flash(error, 'error')
            # Hent udlejere til dropdown
            landlords = User.get_by_role('udlejer')
            return render_template('admin/edit_property.html', property=property_info, landlords=landlords)
        
        # Opdater ejendom
        Property.update(
            property_id=property_id,
            name=name,
            address=address,
            landlord_id=landlord_id
        )
        
        # Håndter filupload hvis der er nogen
        if 'image' in request.files:
            image = request.files['image']
            if image and image.filename != '' and allowed_file(image.filename):
                filename = save_uploaded_file(image, f'property_{property_id}')
                if filename:
                    Property.update_image(property_id, filename)
        
        flash('Ejendom er opdateret med succes!', 'success')
        return redirect(url_for('admin.properties'))
    
    # Hent udlejere til dropdown
    landlords = User.get_by_role('udlejer')
    return render_template('admin/edit_property.html', property=property_info, landlords=landlords)

# CSV import af ejendomme og lejemål
@admin_bp.route('/import', methods=['GET', 'POST'])
@login_required
@admin_required
def import_data():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Ingen fil valgt', 'error')
            return redirect(request.url)
            
        file = request.files['file']
        if file.filename == '':
            flash('Ingen fil valgt', 'error')
            return redirect(request.url)
            
        if file and file.filename.endswith('.csv'):
            # Læs CSV-fil
            csv_data = file.read().decode('utf-8')
            csv_io = io.StringIO(csv_data)
            csv_reader = csv.DictReader(csv_io)
            
            # Importtype (properties, units, tenants)
            import_type = request.form.get('import_type')
            
            # Resultater
            results = {
                'success': 0,
                'errors': []
            }
            
            if import_type == 'properties':
                # Import af ejendomme
                for row in csv_reader:
                    try:
                        name = row.get('name', '').strip()
                        address = row.get('address', '').strip()
                        landlord_email = row.get('landlord_email', '').strip()
                        
                        if not name or not address or not landlord_email:
                            results['errors'].append(f"Manglende data: {row}")
                            continue
                            
                        # Find udlejer baseret på email
                        landlord = User.get_by_email(landlord_email)
                        if not landlord:
                            results['errors'].append(f"Udlejer ikke fundet: {landlord_email}")
                            continue
                            
                        # Opret ejendom
                        Property.create(
                            name=name,
                            address=address,
                            landlord_id=landlord['id']
                        )
                        results['success'] += 1
                        
                    except Exception as e:
                        results['errors'].append(f"Fejl ved import af ejendom: {str(e)}")
                
            elif import_type == 'units':
                # Import af lejemål
                for row in csv_reader:
                    try:
                        property_name = row.get('property_name', '').strip()
                        address = row.get('address', '').strip()
                        floor = row.get('floor', '').strip()
                        size = row.get('size', '').strip()
                        
                        if not property_name or not address:
                            results['errors'].append(f"Manglende data: {row}")
                            continue
                            
                        # Find ejendom baseret på navn
                        property_info = Property.get_by_name(property_name)
                        if not property_info:
                            results['errors'].append(f"Ejendom ikke fundet: {property_name}")
                            continue
                            
                        # Opret lejemål
                        Unit.create(
                            property_id=property_info['id'],
                            address=address,
                            floor=floor,
                            size=size
                        )
                        results['success'] += 1
                        
                    except Exception as e:
                        results['errors'].append(f"Fejl ved import af lejemål: {str(e)}")
                
            elif import_type == 'tenants':
                # Import af lejere
                for row in csv_reader:
                    try:
                        username = row.get('username', '').strip()
                        email = row.get('email', '').strip()
                        unit_address = row.get('unit_address', '').strip()
                        property_name = row.get('property_name', '').strip()
                        
                        if not username or not email or not unit_address or not property_name:
                            results['errors'].append(f"Manglende data: {row}")
                            continue
                            
                        # Find ejendom baseret på navn
                        property_info = Property.get_by_name(property_name)
                        if not property_info:
                            results['errors'].append(f"Ejendom ikke fundet: {property_name}")
                            continue
                            
                        # Find lejemål baseret på adresse og ejendom
                        unit = Unit.get_by_address_and_property(unit_address, property_info['id'])
                        if not unit:
                            results['errors'].append(f"Lejemål ikke fundet: {unit_address} i {property_name}")
                            continue
                            
                        # Tjek om bruger allerede eksisterer
                        existing_user = User.get_by_email(email)
                        if existing_user:
                            # Tilknyt eksisterende bruger til lejemål
                            Unit.assign_tenant(unit['id'], existing_user['id'])
                            results['success'] += 1
                            continue
                            
                        # Opret ny bruger
                        password = User.generate_password()
                        user_id = User.create(
                            username=username,
                            email=email,
                            password=password,
                            role='lejer'
                        )
                        
                        # Tilknyt bruger til lejemål
                        Unit.assign_tenant(unit['id'], user_id)
                        
                        # Her kunne man sende velkomst-email med genereret adgangskode
                        results['success'] += 1
                        
                    except Exception as e:
                        results['errors'].append(f"Fejl ved import af lejer: {str(e)}")
            
            flash(f"Import gennemført. {results['success']} poster importeret. {len(results['errors'])} fejl.", 'info')
            return render_template('admin/import_results.html', results=results)
    
    return render_template('admin/import.html') 