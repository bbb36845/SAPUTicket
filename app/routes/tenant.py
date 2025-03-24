from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
import os
from werkzeug.utils import secure_filename

from app.models.user import User
from app.models.ticket import Ticket
from app.models.unit import Unit
from app.models.property import Property
from app.services.file_service import allowed_file, save_uploaded_file

# Opprettet blueprint for lejer (tenant) routes
tenant_bp = Blueprint('tenant', __name__, url_prefix='/tenant')

# Decorator for at sikre at kun lejere har adgang
def tenant_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'lejer':
            flash('Du har ikke adgang til denne side. Log ind som lejer for at fortsætte.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Dashboard for lejere
@tenant_bp.route('/dashboard')
@login_required
@tenant_required
def dashboard():
    # Hent alle tickets for den aktuelle lejer
    user_units = Unit.get_units_by_tenant(current_user.id)
    unit_ids = [unit['id'] for unit in user_units]
    
    # Filtrerings- og sorteringsparametre
    status_filter = request.args.get('status', '')
    sort_option = request.args.get('sort', 'created_desc')
    
    # Hent tickets baseret på filter og sort
    tickets = Ticket.get_tickets_by_units(unit_ids, status_filter, sort_option)
    
    # Beregn statistik
    total_tickets = len(tickets)
    open_tickets = sum(1 for ticket in tickets if ticket['status'] == 'open')
    in_progress_tickets = sum(1 for ticket in tickets if ticket['status'] == 'in_progress')
    completed_tickets = sum(1 for ticket in tickets if ticket['status'] == 'completed')
    
    stats = {
        'total': total_tickets,
        'open': open_tickets,
        'in_progress': in_progress_tickets,
        'completed': completed_tickets
    }
    
    return render_template('tenant/dashboard.html', 
                           user=current_user,
                           tickets=tickets,
                           stats=stats,
                           status_filter=status_filter,
                           sort_option=sort_option)

# Opret ny service anmodning
@tenant_bp.route('/ticket/create', methods=['GET', 'POST'])
@login_required
@tenant_required
def ticket_create():
    # Hent brugerens lejemål
    user_units = Unit.get_units_by_tenant(current_user.id)
    
    if not user_units:
        flash('Du har ingen registrerede lejemål. Kontakt din udlejer.', 'warning')
        return redirect(url_for('tenant.dashboard'))
    
    if request.method == 'POST':
        # Hent form data
        unit_id = request.form.get('unit_id')
        title = request.form.get('title')
        description = request.form.get('description')
        priority = request.form.get('priority', 'medium')
        
        # Validering
        errors = []
        if not unit_id:
            errors.append('Vælg venligst et lejemål')
        if not title:
            errors.append('Titel er påkrævet')
        if not description:
            errors.append('Beskrivelse er påkrævet')
            
        # Kontroller at unit tilhører brugeren
        unit_belongs_to_user = False
        for unit in user_units:
            if str(unit['id']) == unit_id:
                unit_belongs_to_user = True
                break
                
        if not unit_belongs_to_user:
            errors.append('Det valgte lejemål tilhører ikke dig')
            
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('tenant/create_ticket.html', units=user_units)
        
        # Opret ticket
        ticket_id = Ticket.create(
            tenant_id=current_user.id,
            unit_id=unit_id,
            title=title,
            description=description,
            priority=priority,
            status='open'
        )
        
        # Håndter filupload hvis der er nogen
        if 'images' in request.files:
            images = request.files.getlist('images')
            for image in images:
                if image and image.filename != '' and allowed_file(image.filename):
                    filename = save_uploaded_file(image, f'ticket_{ticket_id}')
                    if filename:
                        Ticket.add_image(ticket_id, filename, current_user.id)
        
        flash('Service anmodning er oprettet med succes!', 'success')
        return redirect(url_for('tenant.ticket_detail', ticket_id=ticket_id))
    
    return render_template('tenant/create_ticket.html', units=user_units)

# Vis ticket detaljer
@tenant_bp.route('/ticket/<int:ticket_id>')
@login_required
@tenant_required
def ticket_detail(ticket_id):
    # Hent ticket
    ticket = Ticket.get_by_id(ticket_id)
    
    if not ticket:
        flash('Service anmodning blev ikke fundet', 'error')
        return redirect(url_for('tenant.dashboard'))
    
    # Sikkerhedstjek: Ticket skal tilhøre brugeren
    user_units = Unit.get_units_by_tenant(current_user.id)
    unit_ids = [unit['id'] for unit in user_units]
    
    if ticket['unit_id'] not in unit_ids:
        flash('Du har ikke adgang til denne service anmodning', 'error')
        return redirect(url_for('tenant.dashboard'))
    
    # Hent billeder og kommentarer
    images = Ticket.get_images(ticket_id)
    comments = Ticket.get_comments(ticket_id)
    unit = Unit.get_by_id(ticket['unit_id'])
    property_info = Property.get_by_id(unit['property_id']) if unit else None
    
    return render_template('tenant/ticket_detail.html',
                           ticket=ticket,
                           images=images,
                           comments=comments,
                           unit=unit,
                           property=property_info)

# Rediger ticket
@tenant_bp.route('/ticket/<int:ticket_id>/edit', methods=['GET', 'POST'])
@login_required
@tenant_required
def ticket_edit(ticket_id):
    # Hent ticket
    ticket = Ticket.get_by_id(ticket_id)
    
    if not ticket:
        flash('Service anmodning blev ikke fundet', 'error')
        return redirect(url_for('tenant.dashboard'))
    
    # Sikkerhedstjek: Ticket skal tilhøre brugeren
    user_units = Unit.get_units_by_tenant(current_user.id)
    unit_ids = [unit['id'] for unit in user_units]
    
    if ticket['unit_id'] not in unit_ids:
        flash('Du har ikke adgang til denne service anmodning', 'error')
        return redirect(url_for('tenant.dashboard'))
    
    # Ticket må kun redigeres hvis den er åben eller på hold
    if ticket['status'] not in ['open', 'on_hold']:
        flash('Denne service anmodning kan ikke redigeres i dens nuværende tilstand', 'warning')
        return redirect(url_for('tenant.ticket_detail', ticket_id=ticket_id))
    
    if request.method == 'POST':
        # Hent form data
        title = request.form.get('title')
        description = request.form.get('description')
        priority = request.form.get('priority', 'medium')
        
        # Validering
        errors = []
        if not title:
            errors.append('Titel er påkrævet')
        if not description:
            errors.append('Beskrivelse er påkrævet')
            
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('tenant/edit_ticket.html', ticket=ticket)
        
        # Opdater ticket
        Ticket.update(
            ticket_id=ticket_id,
            title=title,
            description=description,
            priority=priority
        )
        
        # Håndter filupload hvis der er nogen
        if 'images' in request.files:
            images = request.files.getlist('images')
            for image in images:
                if image and image.filename != '' and allowed_file(image.filename):
                    filename = save_uploaded_file(image, f'ticket_{ticket_id}')
                    if filename:
                        Ticket.add_image(ticket_id, filename, current_user.id)
        
        flash('Service anmodning er opdateret med succes!', 'success')
        return redirect(url_for('tenant.ticket_detail', ticket_id=ticket_id))
    
    # Hent billeder
    images = Ticket.get_images(ticket_id)
    
    return render_template('tenant/edit_ticket.html', ticket=ticket, images=images)

# Annuller ticket
@tenant_bp.route('/ticket/<int:ticket_id>/cancel', methods=['POST'])
@login_required
@tenant_required
def ticket_cancel(ticket_id):
    # Hent ticket
    ticket = Ticket.get_by_id(ticket_id)
    
    if not ticket:
        flash('Service anmodning blev ikke fundet', 'error')
        return redirect(url_for('tenant.dashboard'))
    
    # Sikkerhedstjek: Ticket skal tilhøre brugeren
    user_units = Unit.get_units_by_tenant(current_user.id)
    unit_ids = [unit['id'] for unit in user_units]
    
    if ticket['unit_id'] not in unit_ids:
        flash('Du har ikke adgang til denne service anmodning', 'error')
        return redirect(url_for('tenant.dashboard'))
    
    # Ticket må kun annulleres hvis den er åben, på hold eller igangværende
    if ticket['status'] not in ['open', 'on_hold', 'in_progress']:
        flash('Denne service anmodning kan ikke annulleres i dens nuværende tilstand', 'warning')
        return redirect(url_for('tenant.ticket_detail', ticket_id=ticket_id))
    
    # Annuller ticket
    Ticket.update_status(ticket_id, 'cancelled')
    
    # Tilføj kommentar om annullering
    Ticket.add_comment(
        ticket_id=ticket_id,
        user_id=current_user.id,
        content='Service anmodning annulleret af lejer.'
    )
    
    flash('Service anmodning er blevet annulleret.', 'success')
    return redirect(url_for('tenant.dashboard'))

# Vis oversigt over brugerens lejemål
@tenant_bp.route('/units')
@login_required
@tenant_required
def units():
    # Hent brugerens lejemål
    user_units = Unit.get_units_by_tenant(current_user.id)
    
    for unit in user_units:
        # Hent ejendomsinformation for hver lejlighed
        unit['property'] = Property.get_by_id(unit['property_id'])
        
        # Hent antal tickets for hver lejlighed
        unit_id = unit['id']
        unit['tickets_count'] = Ticket.count_by_unit(unit_id)
        unit['open_tickets'] = Ticket.count_by_unit_and_status(unit_id, 'open')
    
    return render_template('tenant/my_units.html', units=user_units)

# Tilføj kommentar til ticket
@tenant_bp.route('/ticket/<int:ticket_id>/comment', methods=['POST'])
@login_required
@tenant_required
def add_comment(ticket_id):
    # Hent ticket
    ticket = Ticket.get_by_id(ticket_id)
    
    if not ticket:
        flash('Service anmodning blev ikke fundet', 'error')
        return redirect(url_for('tenant.dashboard'))
    
    # Sikkerhedstjek: Ticket skal tilhøre brugeren
    user_units = Unit.get_units_by_tenant(current_user.id)
    unit_ids = [unit['id'] for unit in user_units]
    
    if ticket['unit_id'] not in unit_ids:
        flash('Du har ikke adgang til denne service anmodning', 'error')
        return redirect(url_for('tenant.dashboard'))
    
    # Ticket må ikke være lukket eller færdig
    if ticket['status'] in ['completed', 'cancelled']:
        flash('Du kan ikke tilføje kommentarer til en afsluttet service anmodning', 'warning')
        return redirect(url_for('tenant.ticket_detail', ticket_id=ticket_id))
    
    # Hent kommentarindhold
    content = request.form.get('content', '').strip()
    
    if not content:
        flash('Kommentar kan ikke være tom', 'error')
        return redirect(url_for('tenant.ticket_detail', ticket_id=ticket_id))
    
    # Tilføj kommentar
    Ticket.add_comment(
        ticket_id=ticket_id,
        user_id=current_user.id,
        content=content
    )
    
    # Opdater ticket's opdateringstidspunkt
    Ticket.update_timestamp(ticket_id)
    
    flash('Kommentar er tilføjet', 'success')
    return redirect(url_for('tenant.ticket_detail', ticket_id=ticket_id))

# Vis tickets for en specifik bolig
@tenant_bp.route('/unit/<int:unit_id>/tickets')
@login_required
@tenant_required
def unit_tickets(unit_id):
    # Hent bolig
    unit = Unit.get_by_id(unit_id)
    
    if not unit:
        flash('Bolig ikke fundet', 'error')
        return redirect(url_for('tenant.units'))
    
    # Sikkerhedstjek: Unit skal tilhøre brugeren
    user_units = Unit.get_units_by_tenant(current_user.id)
    user_unit_ids = [u['id'] for u in user_units]
    
    if unit_id not in user_unit_ids:
        flash('Du har ikke adgang til denne bolig', 'error')
        return redirect(url_for('tenant.units'))
    
    # Filtrerings- og sorteringsparametre
    status_filter = request.args.get('status', '')
    sort_option = request.args.get('sort', 'created_desc')
    
    # Hent tickets baseret på filter og sort
    tickets = Ticket.get_tickets_by_unit(unit_id, status_filter, sort_option)
    
    # Hent ejendomsinformation
    property_info = Property.get_by_id(unit['property_id'])
    unit['property'] = property_info
    
    # Beregn statistik
    total_tickets = len(tickets)
    open_tickets = sum(1 for ticket in tickets if ticket['status'] == 'open')
    in_progress_tickets = sum(1 for ticket in tickets if ticket['status'] == 'in_progress')
    completed_tickets = sum(1 for ticket in tickets if ticket['status'] == 'completed')
    
    stats = {
        'total': total_tickets,
        'open': open_tickets,
        'in_progress': in_progress_tickets,
        'completed': completed_tickets
    }
    
    return render_template('tenant/unit_tickets.html',
                           unit=unit,
                           tickets=tickets,
                           stats=stats,
                           status_filter=status_filter,
                           sort_option=sort_option) 