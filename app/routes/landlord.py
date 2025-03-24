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

# Opret blueprint for landlord (udlejer) routes
landlord_bp = Blueprint('landlord', __name__, url_prefix='/landlord')

# Decorator for at sikre at kun udlejere har adgang
def landlord_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'udlejer':
            flash('Du har ikke adgang til denne side. Log ind som udlejer for at fortsætte.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Dashboard for udlejere
@landlord_bp.route('/dashboard')
@login_required
@landlord_required
def dashboard():
    # Hent alle ejendomme for denne udlejer
    properties = Property.get_by_landlord(current_user.id)
    
    # Hent alle lejemål for disse ejendomme
    property_ids = [prop['id'] for prop in properties]
    all_units = Unit.get_by_properties(property_ids)
    
    # Hent alle tickets for disse lejemål
    unit_ids = [unit['id'] for unit in all_units]
    all_tickets = Ticket.get_tickets_by_units(unit_ids, '', 'created_desc')
    
    # Beregn statistik
    total_properties = len(properties)
    total_units = len(all_units)
    
    total_tickets = len(all_tickets)
    open_tickets = sum(1 for ticket in all_tickets if ticket['status'] == 'open')
    in_progress_tickets = sum(1 for ticket in all_tickets if ticket['status'] == 'in_progress')
    completed_tickets = sum(1 for ticket in all_tickets if ticket['status'] == 'completed')
    
    # Hent de seneste 10 tickets
    recent_tickets = sorted(all_tickets, key=lambda x: x.get('updated_at', ''), reverse=True)[:10]
    
    return render_template('landlord/dashboard.html',
                           user=current_user,
                           properties=properties,
                           total_units=total_units,
                           ticket_stats={
                               'total': total_tickets,
                               'open': open_tickets,
                               'in_progress': in_progress_tickets,
                               'completed': completed_tickets
                           },
                           recent_tickets=recent_tickets)

# Vis alle ejendomme
@landlord_bp.route('/properties')
@login_required
@landlord_required
def properties():
    # Hent alle ejendomme for denne udlejer
    properties = Property.get_by_landlord(current_user.id)
    
    # Hent statistik for hver ejendom
    for property_info in properties:
        property_id = property_info['id']
        units = Unit.get_by_property(property_id)
        property_info['units_count'] = len(units)
        
        # Beregn antal tickets for denne ejendom
        unit_ids = [unit['id'] for unit in units]
        tickets = Ticket.get_tickets_by_units(unit_ids, '', '')
        property_info['tickets_count'] = len(tickets)
        property_info['open_tickets'] = sum(1 for ticket in tickets if ticket['status'] == 'open')
    
    return render_template('landlord/properties.html', properties=properties)

# Vis detaljer for en ejendom
@landlord_bp.route('/property/<int:property_id>')
@login_required
@landlord_required
def property_detail(property_id):
    # Hent ejendom
    property_info = Property.get_by_id(property_id)
    
    if not property_info:
        flash('Ejendom ikke fundet', 'error')
        return redirect(url_for('landlord.properties'))
    
    # Sikkerhedstjek: Ejendom skal tilhøre denne udlejer
    if property_info['landlord_id'] != current_user.id:
        flash('Du har ikke adgang til denne ejendom', 'error')
        return redirect(url_for('landlord.properties'))
    
    # Hent alle lejemål for denne ejendom
    units = Unit.get_by_property(property_id)
    
    # Hent statistik for hver lejemål
    for unit in units:
        unit_id = unit['id']
        tickets = Ticket.get_tickets_by_unit(unit_id, '', '')
        unit['tickets_count'] = len(tickets)
        unit['open_tickets'] = sum(1 for ticket in tickets if ticket['status'] == 'open')
        
        # Hent lejerinformation for hver enhed
        tenant_id = unit.get('tenant_id')
        if tenant_id:
            unit['tenant'] = User.get_by_id(tenant_id)
    
    return render_template('landlord/property_detail.html',
                           property=property_info,
                           units=units)

# Opret nyt lejemål
@landlord_bp.route('/property/<int:property_id>/unit/create', methods=['GET', 'POST'])
@login_required
@landlord_required
def create_unit(property_id):
    # Hent ejendom
    property_info = Property.get_by_id(property_id)
    
    if not property_info:
        flash('Ejendom ikke fundet', 'error')
        return redirect(url_for('landlord.properties'))
    
    # Sikkerhedstjek: Ejendom skal tilhøre denne udlejer
    if property_info['landlord_id'] != current_user.id:
        flash('Du har ikke adgang til denne ejendom', 'error')
        return redirect(url_for('landlord.properties'))
    
    if request.method == 'POST':
        # Hent formdata
        address = request.form.get('address')
        floor = request.form.get('floor', '')
        size = request.form.get('size', '')
        
        # Validering
        errors = []
        if not address:
            errors.append('Adresse er påkrævet')
            
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('landlord/create_unit.html', property=property_info)
        
        # Opret lejemål
        unit_id = Unit.create(
            property_id=property_id,
            address=address,
            floor=floor,
            size=size
        )
        
        flash('Lejemål er oprettet med succes!', 'success')
        return redirect(url_for('landlord.property_detail', property_id=property_id))
    
    return render_template('landlord/create_unit.html', property=property_info)

# Rediger lejemål
@landlord_bp.route('/unit/<int:unit_id>/edit', methods=['GET', 'POST'])
@login_required
@landlord_required
def edit_unit(unit_id):
    # Hent lejemål
    unit = Unit.get_by_id(unit_id)
    
    if not unit:
        flash('Lejemål ikke fundet', 'error')
        return redirect(url_for('landlord.properties'))
    
    # Hent ejendom
    property_info = Property.get_by_id(unit['property_id'])
    
    # Sikkerhedstjek: Ejendom skal tilhøre denne udlejer
    if property_info['landlord_id'] != current_user.id:
        flash('Du har ikke adgang til dette lejemål', 'error')
        return redirect(url_for('landlord.properties'))
    
    if request.method == 'POST':
        # Hent formdata
        address = request.form.get('address')
        floor = request.form.get('floor', '')
        size = request.form.get('size', '')
        
        # Validering
        errors = []
        if not address:
            errors.append('Adresse er påkrævet')
            
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('landlord/edit_unit.html', unit=unit, property=property_info)
        
        # Opdater lejemål
        Unit.update(
            unit_id=unit_id,
            address=address,
            floor=floor,
            size=size
        )
        
        flash('Lejemål er opdateret med succes!', 'success')
        return redirect(url_for('landlord.property_detail', property_id=unit['property_id']))
    
    return render_template('landlord/edit_unit.html', unit=unit, property=property_info)

# Tildel lejer til lejemål
@landlord_bp.route('/unit/<int:unit_id>/assign-tenant', methods=['GET', 'POST'])
@login_required
@landlord_required
def assign_tenant(unit_id):
    # Hent lejemål
    unit = Unit.get_by_id(unit_id)
    
    if not unit:
        flash('Lejemål ikke fundet', 'error')
        return redirect(url_for('landlord.properties'))
    
    # Hent ejendom
    property_info = Property.get_by_id(unit['property_id'])
    
    # Sikkerhedstjek: Ejendom skal tilhøre denne udlejer
    if property_info['landlord_id'] != current_user.id:
        flash('Du har ikke adgang til dette lejemål', 'error')
        return redirect(url_for('landlord.properties'))
    
    if request.method == 'POST':
        tenant_email = request.form.get('tenant_email', '').strip()
        
        if not tenant_email:
            flash('E-mail er påkrævet', 'error')
            return render_template('landlord/assign_tenant.html', unit=unit, property=property_info)
        
        # Tjek om bruger allerede eksisterer
        tenant = User.get_by_email(tenant_email)
        
        if tenant:
            # Eksisterende bruger - tildel til lejemålet
            Unit.assign_tenant(unit_id, tenant['id'])
            flash(f"Lejemål tildelt til eksisterende bruger: {tenant['username']}", 'success')
        else:
            # Opret ny bruger
            username = tenant_email.split('@')[0]  # Simpel brugernavn fra email
            password = User.generate_password()
            
            tenant_id = User.create(
                username=username,
                email=tenant_email,
                password=password,
                role='lejer'
            )
            
            # Tildel ny bruger til lejemålet
            Unit.assign_tenant(unit_id, tenant_id)
            
            # Her kunne man sende velkomst-email med genereret adgangskode
            flash(f"Ny lejer oprettet med brugernavn: {username} og password: {password}", 'success')
        
        return redirect(url_for('landlord.property_detail', property_id=unit['property_id']))
    
    return render_template('landlord/assign_tenant.html', unit=unit, property=property_info)

# Fjern lejer fra lejemål
@landlord_bp.route('/unit/<int:unit_id>/remove-tenant', methods=['POST'])
@login_required
@landlord_required
def remove_tenant(unit_id):
    # Hent lejemål
    unit = Unit.get_by_id(unit_id)
    
    if not unit:
        flash('Lejemål ikke fundet', 'error')
        return redirect(url_for('landlord.properties'))
    
    # Hent ejendom
    property_info = Property.get_by_id(unit['property_id'])
    
    # Sikkerhedstjek: Ejendom skal tilhøre denne udlejer
    if property_info['landlord_id'] != current_user.id:
        flash('Du har ikke adgang til dette lejemål', 'error')
        return redirect(url_for('landlord.properties'))
    
    # Fjern lejer fra lejemålet
    Unit.remove_tenant(unit_id)
    
    flash('Lejer er fjernet fra lejemålet', 'success')
    return redirect(url_for('landlord.property_detail', property_id=unit['property_id']))

# Vis alle tickets
@landlord_bp.route('/tickets')
@login_required
@landlord_required
def tickets():
    # Hent alle ejendomme for denne udlejer
    properties = Property.get_by_landlord(current_user.id)
    
    # Hent alle lejemål for disse ejendomme
    property_ids = [prop['id'] for prop in properties]
    all_units = Unit.get_by_properties(property_ids)
    
    # Hent filter og sortering
    status_filter = request.args.get('status', '')
    sort_option = request.args.get('sort', 'created_desc')
    
    # Hent alle tickets for disse lejemål
    unit_ids = [unit['id'] for unit in all_units]
    tickets = Ticket.get_tickets_by_units(unit_ids, status_filter, sort_option)
    
    # Optionel filtrering på ejendom
    property_filter = request.args.get('property_id', '')
    if property_filter:
        property_units = [unit['id'] for unit in all_units if str(unit['property_id']) == property_filter]
        tickets = [ticket for ticket in tickets if ticket['unit_id'] in property_units]
    
    return render_template('landlord/tickets.html',
                           tickets=tickets,
                           properties=properties,
                           status_filter=status_filter,
                           sort_option=sort_option,
                           property_filter=property_filter)

# Vis en specifik ticket
@landlord_bp.route('/ticket/<int:ticket_id>')
@login_required
@landlord_required
def ticket_detail(ticket_id):
    # Hent ticket
    ticket = Ticket.get_by_id(ticket_id)
    
    if not ticket:
        flash('Service anmodning blev ikke fundet', 'error')
        return redirect(url_for('landlord.tickets'))
    
    # Hent lejemål og ejendom
    unit = Unit.get_by_id(ticket['unit_id'])
    if not unit:
        flash('Lejemål ikke fundet', 'error')
        return redirect(url_for('landlord.tickets'))
    
    property_info = Property.get_by_id(unit['property_id'])
    
    # Sikkerhedstjek: Ejendom skal tilhøre denne udlejer
    if property_info['landlord_id'] != current_user.id:
        flash('Du har ikke adgang til denne service anmodning', 'error')
        return redirect(url_for('landlord.tickets'))
    
    # Hent billeder og kommentarer
    images = Ticket.get_images(ticket_id)
    comments = Ticket.get_comments(ticket_id)
    
    # Hent tenant info
    tenant = User.get_by_id(ticket['tenant_id']) if ticket.get('tenant_id') else None
    
    # Hent craftsman info hvis tilknyttet
    craftsman = None
    if ticket.get('craftsman_id'):
        craftsman = User.get_by_id(ticket['craftsman_id'])
    
    return render_template('landlord/ticket_detail.html',
                           ticket=ticket,
                           unit=unit,
                           property=property_info,
                           tenant=tenant,
                           craftsman=craftsman,
                           images=images,
                           comments=comments)

# Opdater ticket status
@landlord_bp.route('/ticket/<int:ticket_id>/update-status', methods=['POST'])
@login_required
@landlord_required
def update_ticket_status(ticket_id):
    # Hent ticket
    ticket = Ticket.get_by_id(ticket_id)
    
    if not ticket:
        flash('Service anmodning blev ikke fundet', 'error')
        return redirect(url_for('landlord.tickets'))
    
    # Hent lejemål og ejendom
    unit = Unit.get_by_id(ticket['unit_id'])
    if not unit:
        flash('Lejemål ikke fundet', 'error')
        return redirect(url_for('landlord.tickets'))
    
    property_info = Property.get_by_id(unit['property_id'])
    
    # Sikkerhedstjek: Ejendom skal tilhøre denne udlejer
    if property_info['landlord_id'] != current_user.id:
        flash('Du har ikke adgang til denne service anmodning', 'error')
        return redirect(url_for('landlord.tickets'))
    
    # Hent ny status
    new_status = request.form.get('status')
    if not new_status:
        flash('Status er påkrævet', 'error')
        return redirect(url_for('landlord.ticket_detail', ticket_id=ticket_id))
    
    # Opdater status
    Ticket.update_status(ticket_id, new_status)
    
    # Tilføj kommentar om statusændring
    Ticket.add_comment(
        ticket_id=ticket_id,
        user_id=current_user.id,
        content=f'Status ændret til: {new_status}'
    )
    
    flash('Status opdateret med succes!', 'success')
    return redirect(url_for('landlord.ticket_detail', ticket_id=ticket_id))

# Tilføj kommentar til ticket
@landlord_bp.route('/ticket/<int:ticket_id>/comment', methods=['POST'])
@login_required
@landlord_required
def add_comment(ticket_id):
    # Hent ticket
    ticket = Ticket.get_by_id(ticket_id)
    
    if not ticket:
        flash('Service anmodning blev ikke fundet', 'error')
        return redirect(url_for('landlord.tickets'))
    
    # Hent lejemål og ejendom
    unit = Unit.get_by_id(ticket['unit_id'])
    if not unit:
        flash('Lejemål ikke fundet', 'error')
        return redirect(url_for('landlord.tickets'))
    
    property_info = Property.get_by_id(unit['property_id'])
    
    # Sikkerhedstjek: Ejendom skal tilhøre denne udlejer
    if property_info['landlord_id'] != current_user.id:
        flash('Du har ikke adgang til denne service anmodning', 'error')
        return redirect(url_for('landlord.tickets'))
    
    # Hent kommentarindhold
    content = request.form.get('content', '').strip()
    
    if not content:
        flash('Kommentar kan ikke være tom', 'error')
        return redirect(url_for('landlord.ticket_detail', ticket_id=ticket_id))
    
    # Tilføj kommentar
    Ticket.add_comment(
        ticket_id=ticket_id,
        user_id=current_user.id,
        content=content
    )
    
    # Opdater ticket's opdateringstidspunkt
    Ticket.update_timestamp(ticket_id)
    
    flash('Kommentar er tilføjet', 'success')
    return redirect(url_for('landlord.ticket_detail', ticket_id=ticket_id))

# Tildel håndværker til ticket
@landlord_bp.route('/ticket/<int:ticket_id>/assign-craftsman', methods=['GET', 'POST'])
@login_required
@landlord_required
def assign_craftsman(ticket_id):
    # Hent ticket
    ticket = Ticket.get_by_id(ticket_id)
    
    if not ticket:
        flash('Service anmodning blev ikke fundet', 'error')
        return redirect(url_for('landlord.tickets'))
    
    # Hent lejemål og ejendom
    unit = Unit.get_by_id(ticket['unit_id'])
    if not unit:
        flash('Lejemål ikke fundet', 'error')
        return redirect(url_for('landlord.tickets'))
    
    property_info = Property.get_by_id(unit['property_id'])
    
    # Sikkerhedstjek: Ejendom skal tilhøre denne udlejer
    if property_info['landlord_id'] != current_user.id:
        flash('Du har ikke adgang til denne service anmodning', 'error')
        return redirect(url_for('landlord.tickets'))
    
    if request.method == 'POST':
        craftsman_id = request.form.get('craftsman_id')
        requires_bid = request.form.get('requires_bid') == 'on'
        
        if not craftsman_id:
            flash('Håndværker er påkrævet', 'error')
            # Hent alle håndværkere
            craftsmen = User.get_by_role('craftsman')
            return render_template('landlord/assign_craftsman.html', 
                                   ticket=ticket, 
                                   unit=unit,
                                   property=property_info,
                                   craftsmen=craftsmen)
        
        # Tildel håndværker til ticket
        Ticket.assign_craftsman(
            ticket_id=ticket_id,
            craftsman_id=craftsman_id,
            requires_bid=requires_bid
        )
        
        # Tilføj kommentar
        Ticket.add_comment(
            ticket_id=ticket_id,
            user_id=current_user.id,
            content=f'Håndværker tildelt til denne service anmodning'
        )
        
        flash('Håndværker er tildelt med succes!', 'success')
        return redirect(url_for('landlord.ticket_detail', ticket_id=ticket_id))
    
    # Hent alle håndværkere
    craftsmen = User.get_by_role('craftsman')
    return render_template('landlord/assign_craftsman.html', 
                           ticket=ticket, 
                           unit=unit,
                           property=property_info,
                           craftsmen=craftsmen) 