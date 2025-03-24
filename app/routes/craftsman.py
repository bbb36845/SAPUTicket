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

# Opret blueprint for craftsman (håndværker) routes
craftsman_bp = Blueprint('craftsman', __name__, url_prefix='/craftsman')

# Decorator for at sikre at kun håndværkere har adgang
def craftsman_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'craftsman':
            flash('Du har ikke adgang til denne side. Log ind som håndværker for at fortsætte.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Dashboard for håndværkere
@craftsman_bp.route('/dashboard')
@login_required
@craftsman_required
def dashboard():
    # Hent alle tickets tildelt til denne håndværker
    tickets = Ticket.get_by_craftsman(current_user.id)
    
    # Filtrerings- og sorteringsparametre
    status_filter = request.args.get('status', '')
    sort_option = request.args.get('sort', 'updated_desc')
    
    # Filtrer tickets baseret på status
    if status_filter:
        if status_filter == 'open':
            tickets = [t for t in tickets if t['status'] == 'open']
        elif status_filter == 'in_progress':
            tickets = [t for t in tickets if t['status'] == 'in_progress']
        elif status_filter == 'completed':
            tickets = [t for t in tickets if t['status'] == 'completed']
        elif status_filter == 'on_hold':
            tickets = [t for t in tickets if t['status'] == 'on_hold']
            
    # Sorter tickets
    if sort_option == 'created_asc':
        tickets = sorted(tickets, key=lambda x: x.get('created_at', ''))
    elif sort_option == 'created_desc':
        tickets = sorted(tickets, key=lambda x: x.get('created_at', ''), reverse=True)
    elif sort_option == 'updated_asc':
        tickets = sorted(tickets, key=lambda x: x.get('updated_at', ''))
    elif sort_option == 'updated_desc':
        tickets = sorted(tickets, key=lambda x: x.get('updated_at', ''), reverse=True)
    elif sort_option == 'priority_high':
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        tickets = sorted(tickets, key=lambda x: priority_order.get(x.get('priority'), 3))
    
    # Beregn statistik
    total_tickets = len(tickets)
    pending_approval = sum(1 for ticket in tickets if ticket.get('craftsman_status') == 'pending')
    requires_bid = sum(1 for ticket in tickets if ticket.get('requires_bid') == True)
    open_tickets = sum(1 for ticket in tickets if ticket['status'] == 'open')
    in_progress_tickets = sum(1 for ticket in tickets if ticket['status'] == 'in_progress')
    completed_tickets = sum(1 for ticket in tickets if ticket['status'] == 'completed')
    
    stats = {
        'total': total_tickets,
        'pending_approval': pending_approval,
        'requires_bid': requires_bid,
        'open': open_tickets,
        'in_progress': in_progress_tickets,
        'completed': completed_tickets
    }
    
    return render_template('craftsman/dashboard.html',
                           user=current_user,
                           tickets=tickets,
                           stats=stats,
                           status_filter=status_filter,
                           sort_option=sort_option)

# Vis en specifik ticket
@craftsman_bp.route('/ticket/<int:ticket_id>')
@login_required
@craftsman_required
def ticket_detail(ticket_id):
    # Hent ticket
    ticket = Ticket.get_by_id(ticket_id)
    
    if not ticket:
        flash('Service anmodning blev ikke fundet', 'error')
        return redirect(url_for('craftsman.dashboard'))
    
    # Sikkerhedstjek: Ticket skal være tildelt denne håndværker
    if ticket.get('craftsman_id') != current_user.id:
        flash('Du har ikke adgang til denne service anmodning', 'error')
        return redirect(url_for('craftsman.dashboard'))
    
    # Hent lejemål og ejendom
    unit = Unit.get_by_id(ticket['unit_id'])
    property_info = None
    if unit:
        property_info = Property.get_by_id(unit['property_id'])
    
    # Hent billeder og kommentarer
    images = Ticket.get_images(ticket_id)
    comments = Ticket.get_comments(ticket_id)
    
    # Hent tenant og landlord info
    tenant = None
    if ticket.get('tenant_id'):
        tenant = User.get_by_id(ticket['tenant_id'])
    
    landlord = None
    if property_info and property_info.get('landlord_id'):
        landlord = User.get_by_id(property_info['landlord_id'])
    
    # Tjek om tilbud er påkrævet og givet
    bid = Ticket.get_bid(ticket_id, current_user.id)
    
    return render_template('craftsman/ticket_detail.html',
                           ticket=ticket,
                           unit=unit,
                           property=property_info,
                           tenant=tenant,
                           landlord=landlord,
                           images=images,
                           comments=comments,
                           bid=bid)

# Opdater ticket status
@craftsman_bp.route('/ticket/<int:ticket_id>/update-status', methods=['POST'])
@login_required
@craftsman_required
def update_ticket_status(ticket_id):
    # Hent ticket
    ticket = Ticket.get_by_id(ticket_id)
    
    if not ticket:
        flash('Service anmodning blev ikke fundet', 'error')
        return redirect(url_for('craftsman.dashboard'))
    
    # Sikkerhedstjek: Ticket skal være tildelt denne håndværker
    if ticket.get('craftsman_id') != current_user.id:
        flash('Du har ikke adgang til denne service anmodning', 'error')
        return redirect(url_for('craftsman.dashboard'))
    
    # Tjek at håndværker er godkendt til denne ticket
    if ticket.get('craftsman_status') != 'approved':
        flash('Du kan ikke opdatere status for denne service anmodning endnu', 'error')
        return redirect(url_for('craftsman.ticket_detail', ticket_id=ticket_id))
    
    # Hent ny status
    new_status = request.form.get('status')
    if not new_status:
        flash('Status er påkrævet', 'error')
        return redirect(url_for('craftsman.ticket_detail', ticket_id=ticket_id))
    
    # Kun tilladte status-ændringer
    allowed_transitions = {
        'open': ['in_progress'],
        'in_progress': ['on_hold', 'completed'],
        'on_hold': ['in_progress']
    }
    
    current_status = ticket['status']
    if new_status not in allowed_transitions.get(current_status, []):
        flash(f'Kan ikke ændre status fra {current_status} til {new_status}', 'error')
        return redirect(url_for('craftsman.ticket_detail', ticket_id=ticket_id))
    
    # Opdater status
    Ticket.update_status(ticket_id, new_status)
    
    # Tilføj kommentar om statusændring
    Ticket.add_comment(
        ticket_id=ticket_id,
        user_id=current_user.id,
        content=f'Status ændret til: {new_status}'
    )
    
    flash('Status opdateret med succes!', 'success')
    return redirect(url_for('craftsman.ticket_detail', ticket_id=ticket_id))

# Tilføj kommentar til ticket
@craftsman_bp.route('/ticket/<int:ticket_id>/comment', methods=['POST'])
@login_required
@craftsman_required
def add_comment(ticket_id):
    # Hent ticket
    ticket = Ticket.get_by_id(ticket_id)
    
    if not ticket:
        flash('Service anmodning blev ikke fundet', 'error')
        return redirect(url_for('craftsman.dashboard'))
    
    # Sikkerhedstjek: Ticket skal være tildelt denne håndværker
    if ticket.get('craftsman_id') != current_user.id:
        flash('Du har ikke adgang til denne service anmodning', 'error')
        return redirect(url_for('craftsman.dashboard'))
    
    # Hent kommentarindhold
    content = request.form.get('content', '').strip()
    
    if not content:
        flash('Kommentar kan ikke være tom', 'error')
        return redirect(url_for('craftsman.ticket_detail', ticket_id=ticket_id))
    
    # Tilføj kommentar
    Ticket.add_comment(
        ticket_id=ticket_id,
        user_id=current_user.id,
        content=content
    )
    
    # Opdater ticket's opdateringstidspunkt
    Ticket.update_timestamp(ticket_id)
    
    flash('Kommentar er tilføjet', 'success')
    return redirect(url_for('craftsman.ticket_detail', ticket_id=ticket_id))

# Tilføj tilbud til ticket
@craftsman_bp.route('/ticket/<int:ticket_id>/add-bid', methods=['GET', 'POST'])
@login_required
@craftsman_required
def add_bid(ticket_id):
    # Hent ticket
    ticket = Ticket.get_by_id(ticket_id)
    
    if not ticket:
        flash('Service anmodning blev ikke fundet', 'error')
        return redirect(url_for('craftsman.dashboard'))
    
    # Sikkerhedstjek: Ticket skal være tildelt denne håndværker
    if ticket.get('craftsman_id') != current_user.id:
        flash('Du har ikke adgang til denne service anmodning', 'error')
        return redirect(url_for('craftsman.dashboard'))
    
    # Tjek at håndværker er godkendt til denne ticket
    if ticket.get('craftsman_status') != 'approved':
        flash('Du kan ikke afgive tilbud på denne service anmodning endnu', 'error')
        return redirect(url_for('craftsman.ticket_detail', ticket_id=ticket_id))
    
    # Tjek at der kræves tilbud
    if not ticket.get('requires_bid'):
        flash('Der kræves ikke tilbud for denne service anmodning', 'error')
        return redirect(url_for('craftsman.ticket_detail', ticket_id=ticket_id))
    
    # Tjek om der allerede er givet et tilbud
    existing_bid = Ticket.get_bid(ticket_id, current_user.id)
    
    if request.method == 'POST':
        # Hent formdata
        amount = request.form.get('amount', '').strip()
        description = request.form.get('description', '').strip()
        estimated_hours = request.form.get('estimated_hours', '').strip()
        
        # Validering
        errors = []
        if not amount:
            errors.append('Beløb er påkrævet')
        if not description:
            errors.append('Beskrivelse er påkrævet')
            
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('craftsman/add_bid.html', ticket=ticket, existing_bid=existing_bid)
        
        try:
            amount = float(amount.replace(',', '.'))
        except ValueError:
            flash('Beløb skal være et tal', 'error')
            return render_template('craftsman/add_bid.html', ticket=ticket, existing_bid=existing_bid)
        
        # Opret eller opdater tilbud
        if existing_bid:
            Ticket.update_bid(
                ticket_id=ticket_id,
                craftsman_id=current_user.id,
                amount=amount,
                description=description,
                estimated_hours=estimated_hours
            )
            flash('Tilbud er opdateret med succes!', 'success')
        else:
            Ticket.add_bid(
                ticket_id=ticket_id,
                craftsman_id=current_user.id,
                amount=amount,
                description=description,
                estimated_hours=estimated_hours
            )
            
            # Tilføj kommentar om nyt tilbud
            Ticket.add_comment(
                ticket_id=ticket_id,
                user_id=current_user.id,
                content=f'Tilbud afgivet på {amount} kr.'
            )
            
            flash('Tilbud er afgivet med succes!', 'success')
        
        return redirect(url_for('craftsman.ticket_detail', ticket_id=ticket_id))
    
    return render_template('craftsman/add_bid.html', ticket=ticket, existing_bid=existing_bid)

# Accepter tildeling af ticket
@craftsman_bp.route('/ticket/<int:ticket_id>/accept', methods=['POST'])
@login_required
@craftsman_required
def accept_ticket(ticket_id):
    # Hent ticket
    ticket = Ticket.get_by_id(ticket_id)
    
    if not ticket:
        flash('Service anmodning blev ikke fundet', 'error')
        return redirect(url_for('craftsman.dashboard'))
    
    # Sikkerhedstjek: Ticket skal være tildelt denne håndværker
    if ticket.get('craftsman_id') != current_user.id:
        flash('Du har ikke adgang til denne service anmodning', 'error')
        return redirect(url_for('craftsman.dashboard'))
    
    # Tjek at håndværker ikke allerede er godkendt
    if ticket.get('craftsman_status') == 'approved':
        flash('Du er allerede godkendt til denne service anmodning', 'warning')
        return redirect(url_for('craftsman.ticket_detail', ticket_id=ticket_id))
    
    # Opdater craftsman_status til 'approved'
    Ticket.approve_craftsman(ticket_id)
    
    # Tilføj kommentar
    Ticket.add_comment(
        ticket_id=ticket_id,
        user_id=current_user.id,
        content='Håndværker har accepteret tildeling af service anmodning'
    )
    
    flash('Du har accepteret tildelingen af denne service anmodning', 'success')
    return redirect(url_for('craftsman.ticket_detail', ticket_id=ticket_id))

# Afvis tildeling af ticket
@craftsman_bp.route('/ticket/<int:ticket_id>/decline', methods=['POST'])
@login_required
@craftsman_required
def decline_ticket(ticket_id):
    # Hent ticket
    ticket = Ticket.get_by_id(ticket_id)
    
    if not ticket:
        flash('Service anmodning blev ikke fundet', 'error')
        return redirect(url_for('craftsman.dashboard'))
    
    # Sikkerhedstjek: Ticket skal være tildelt denne håndværker
    if ticket.get('craftsman_id') != current_user.id:
        flash('Du har ikke adgang til denne service anmodning', 'error')
        return redirect(url_for('craftsman.dashboard'))
    
    # Opdater craftsman_id til NULL
    Ticket.remove_craftsman(ticket_id)
    
    # Tilføj kommentar
    Ticket.add_comment(
        ticket_id=ticket_id,
        user_id=current_user.id,
        content='Håndværker har afvist tildeling af service anmodning'
    )
    
    flash('Du har afvist tildelingen af denne service anmodning', 'success')
    return redirect(url_for('craftsman.dashboard')) 