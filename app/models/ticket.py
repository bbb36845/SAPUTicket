import uuid
from datetime import datetime
from app.db import get_db_connection

class Ticket:
    """Klasse der repræsenterer en serviceanmodning/ticket"""
    
    # Status konstanter
    STATUS_CREATED = 'Oprettet'
    STATUS_IN_PROGRESS = 'Igangsat'
    STATUS_AWAITING = 'Afventer'
    STATUS_COMPLETED = 'Afsluttet'
    STATUS_CLOSED = 'Lukket'
    
    # Liste over tilgængelige statusser
    STATUS_LIST = [
        STATUS_CREATED,
        STATUS_IN_PROGRESS,
        STATUS_AWAITING,
        STATUS_COMPLETED,
        STATUS_CLOSED
    ]
    
    def __init__(self, id=None, title=None, description=None, unit_id=None, 
                 created_by=None, status=None, priority=None, category=None,
                 assigned_to=None, created_at=None, updated_at=None):
        """Initialiserer et Ticket objekt"""
        self.id = id
        self.title = title
        self.description = description
        self.unit_id = unit_id
        self.created_by = created_by
        self.status = status or self.STATUS_CREATED
        self.priority = priority or 'Medium'
        self.category = category
        self.assigned_to = assigned_to
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
    
    @staticmethod
    def from_dict(ticket_dict):
        """Opretter et Ticket objekt fra en dictionary (typisk fra databasen)"""
        if not ticket_dict:
            return None
        return Ticket(
            id=ticket_dict['id'],
            title=ticket_dict['title'],
            description=ticket_dict['description'],
            unit_id=ticket_dict['unit_id'],
            created_by=ticket_dict['created_by'],
            status=ticket_dict['status'],
            priority=ticket_dict['priority'],
            category=ticket_dict['category'],
            assigned_to=ticket_dict['assigned_to'],
            created_at=ticket_dict.get('created_at'),
            updated_at=ticket_dict.get('updated_at')
        )
    
    @staticmethod
    def get_by_id(ticket_id):
        """Henter en ticket fra databasen baseret på ID"""
        conn = get_db_connection()
        ticket_data = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
        conn.close()
        return Ticket.from_dict(ticket_data) if ticket_data else None
    
    @staticmethod
    def get_by_unit(unit_id):
        """Henter alle tickets for en bestemt lejlighed"""
        conn = get_db_connection()
        tickets = conn.execute('SELECT * FROM tickets WHERE unit_id = ? ORDER BY created_at DESC', 
                             (unit_id,)).fetchall()
        conn.close()
        return [Ticket.from_dict(ticket) for ticket in tickets]
    
    @staticmethod
    def get_by_property(property_id):
        """Henter alle tickets for en bestemt ejendom via enhederne"""
        conn = get_db_connection()
        tickets = conn.execute('''
            SELECT t.* FROM tickets t
            JOIN units u ON t.unit_id = u.id
            WHERE u.property_id = ?
            ORDER BY t.created_at DESC
        ''', (property_id,)).fetchall()
        conn.close()
        return [Ticket.from_dict(ticket) for ticket in tickets]
    
    @staticmethod
    def get_by_created_by(user_id):
        """Henter alle tickets oprettet af en bestemt bruger"""
        conn = get_db_connection()
        tickets = conn.execute('SELECT * FROM tickets WHERE created_by = ? ORDER BY created_at DESC', 
                             (user_id,)).fetchall()
        conn.close()
        return [Ticket.from_dict(ticket) for ticket in tickets]
    
    @staticmethod
    def get_by_assigned_to(user_id):
        """Henter alle tickets tildelt til en bestemt bruger/håndværker"""
        conn = get_db_connection()
        tickets = conn.execute('SELECT * FROM tickets WHERE assigned_to = ? ORDER BY created_at DESC', 
                             (user_id,)).fetchall()
        conn.close()
        return [Ticket.from_dict(ticket) for ticket in tickets]
    
    @staticmethod
    def get_by_landlord(landlord_id):
        """Henter alle tickets for ejendomme, der ejes af en bestemt udlejer"""
        conn = get_db_connection()
        tickets = conn.execute('''
            SELECT t.* FROM tickets t
            JOIN units u ON t.unit_id = u.id
            JOIN properties p ON u.property_id = p.id
            WHERE p.landlord_id = ?
            ORDER BY t.created_at DESC
        ''', (landlord_id,)).fetchall()
        conn.close()
        return [Ticket.from_dict(ticket) for ticket in tickets]
    
    @staticmethod
    def get_all():
        """Henter alle tickets fra databasen"""
        conn = get_db_connection()
        tickets = conn.execute('SELECT * FROM tickets ORDER BY created_at DESC').fetchall()
        conn.close()
        return [Ticket.from_dict(ticket) for ticket in tickets]
    
    def save(self):
        """Gemmer eller opdaterer ticket i databasen"""
        conn = get_db_connection()
        now = datetime.now()
        
        if self.id is None:
            # Opret ny ticket
            self.id = conn.execute('''
                INSERT INTO tickets (title, description, unit_id, created_by, status, priority, category, assigned_to, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (self.title, self.description, self.unit_id, self.created_by, self.status, self.priority, self.category, self.assigned_to, now, now)).lastrowid
            
            # Tilføj til ticket_history ved oprettelse
            add_ticket_history(self.id, self.created_by, None, self.STATUS_CREATED, 'Ticket oprettet')
        else:
            # Hent den eksisterende ticket for at finde den tidligere status
            old_ticket = Ticket.get_by_id(self.id)
            old_status = old_ticket.status if old_ticket else None
            
            # Opdater eksisterende ticket
            self.updated_at = now
            conn.execute('''
                UPDATE tickets 
                SET title = ?, description = ?, unit_id = ?, status = ?, 
                    priority = ?, category = ?, assigned_to = ?, updated_at = ?
                WHERE id = ?
            ''', (self.title, self.description, self.unit_id, self.status, 
                 self.priority, self.category, self.assigned_to, now, self.id))
            
            # Hvis status er ændret, tilføj historik
            if old_status and old_status != self.status:
                from flask_login import current_user
                user_id = current_user.id if hasattr(current_user, 'id') else self.created_by
                add_ticket_history(self.id, user_id, old_status, self.status, f'Status ændret fra {old_status} til {self.status}')
        
        conn.commit()
        conn.close()
        return self.id
    
    def delete(self):
        """Sletter ticket fra databasen"""
        conn = get_db_connection()
        conn.execute('DELETE FROM tickets WHERE id = ?', (self.id,))
        conn.commit()
        conn.close()
        return True
    
    def to_dict(self):
        """Konverterer objektet til en dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'unit_id': self.unit_id,
            'created_by': self.created_by,
            'status': self.status,
            'priority': self.priority,
            'category': self.category,
            'assigned_to': self.assigned_to,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def get_unit(self):
        """Henter den tilhørende lejlighedsenhed for denne ticket"""
        from app.models.unit import Unit
        return Unit.get_by_id(self.unit_id)
    
    def get_creator(self):
        """Henter brugeren der oprettede denne ticket"""
        from app.models.user import User
        return User.get_by_id(self.created_by)
    
    def get_assignee(self):
        """Henter brugeren der er tildelt denne ticket, hvis der er en"""
        if not self.assigned_to:
            return None
        from app.models.user import User
        return User.get_by_id(self.assigned_to)
    
    def get_history(self):
        """Henter historikken for denne ticket"""
        return get_ticket_history(self.id)
    
    def get_comments(self):
        """Henter kommentarer for denne ticket"""
        return get_ticket_comments(self.id)
    
    def get_images(self):
        """Henter billeder for denne ticket"""
        from app.services.file_service import get_ticket_images
        return get_ticket_images(self.id)
    
    def get_documents(self):
        """Henter dokumenter for denne ticket"""
        from app.services.file_service import get_ticket_documents
        return get_ticket_documents(self.id)
    
    def get_bids(self):
        """Henter tilbud for denne ticket"""
        return get_ticket_bids(self.id)

# Hjælpefunktioner for ticket-relaterede operationer
def add_ticket_history(ticket_id, user_id, old_status, new_status, comment):
    """Tilføjer en ændring til ticket historikken"""
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO ticket_history (ticket_id, user_id, old_status, new_status, comment, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (ticket_id, user_id, old_status, new_status, comment, datetime.now()))
    conn.commit()
    conn.close()

def get_ticket_history(ticket_id):
    """Henter historikken for en bestemt ticket"""
    conn = get_db_connection()
    history = conn.execute('''
        SELECT h.*, u.username 
        FROM ticket_history h
        LEFT JOIN users u ON h.user_id = u.id
        WHERE h.ticket_id = ?
        ORDER BY h.created_at ASC
    ''', (ticket_id,)).fetchall()
    conn.close()
    return history

def add_ticket_comment(ticket_id, user_id, comment):
    """Tilføjer en kommentar til en ticket"""
    conn = get_db_connection()
    comment_id = conn.execute('''
        INSERT INTO ticket_comments (ticket_id, user_id, comment, created_at)
        VALUES (?, ?, ?, ?)
    ''', (ticket_id, user_id, comment, datetime.now())).lastrowid
    conn.commit()
    conn.close()
    
    # Tilføj også en historik-post om kommentaren
    add_ticket_history(ticket_id, user_id, None, None, 'Kommentar tilføjet')
    
    return comment_id

def get_ticket_comments(ticket_id):
    """Henter kommentarer for en bestemt ticket"""
    conn = get_db_connection()
    comments = conn.execute('''
        SELECT c.*, u.username 
        FROM ticket_comments c
        LEFT JOIN users u ON c.user_id = u.id
        WHERE c.ticket_id = ?
        ORDER BY c.created_at ASC
    ''', (ticket_id,)).fetchall()
    conn.close()
    return comments

def get_ticket_bids(ticket_id):
    """Henter tilbud for en bestemt ticket"""
    conn = get_db_connection()
    bids = conn.execute('''
        SELECT b.*, u.username 
        FROM bids b
        LEFT JOIN users u ON b.craftsman_id = u.id
        WHERE b.ticket_id = ?
        ORDER BY b.created_at ASC
    ''', (ticket_id,)).fetchall()
    conn.close()
    return bids 