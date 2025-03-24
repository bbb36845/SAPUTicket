import uuid
from datetime import datetime
from app.db import get_db_connection

class Unit:
    """Klasse der repræsenterer en lejlighedsenhed"""
    
    def __init__(self, id=None, property_id=None, unit_number=None, floor=None, 
                 size=None, rooms=None, tenant_id=None, created_at=None, updated_at=None):
        """Initialiserer et Unit objekt"""
        self.id = id
        self.property_id = property_id
        self.unit_number = unit_number
        self.floor = floor
        self.size = size
        self.rooms = rooms
        self.tenant_id = tenant_id
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
    
    @staticmethod
    def from_dict(unit_dict):
        """Opretter et Unit objekt fra en dictionary (typisk fra databasen)"""
        if not unit_dict:
            return None
        return Unit(
            id=unit_dict['id'],
            property_id=unit_dict['property_id'],
            unit_number=unit_dict['unit_number'],
            floor=unit_dict['floor'],
            size=unit_dict['size'],
            rooms=unit_dict['rooms'],
            tenant_id=unit_dict['tenant_id'],
            created_at=unit_dict.get('created_at'),
            updated_at=unit_dict.get('updated_at')
        )
    
    @staticmethod
    def get_by_id(unit_id):
        """Henter en lejlighedsenhed fra databasen baseret på ID"""
        conn = get_db_connection()
        unit_data = conn.execute('SELECT * FROM units WHERE id = ?', (unit_id,)).fetchone()
        conn.close()
        return Unit.from_dict(unit_data) if unit_data else None
    
    @staticmethod
    def get_by_property(property_id):
        """Henter alle lejlighedsenheder for en bestemt ejendom"""
        conn = get_db_connection()
        units = conn.execute('SELECT * FROM units WHERE property_id = ?', (property_id,)).fetchall()
        conn.close()
        return [Unit.from_dict(unit) for unit in units]
    
    @staticmethod
    def get_by_tenant(tenant_id):
        """Henter alle lejlighedsenheder for en bestemt lejer"""
        conn = get_db_connection()
        units = conn.execute('SELECT * FROM units WHERE tenant_id = ?', (tenant_id,)).fetchall()
        conn.close()
        return [Unit.from_dict(unit) for unit in units]
    
    @staticmethod
    def get_all():
        """Henter alle lejlighedsenheder fra databasen"""
        conn = get_db_connection()
        units = conn.execute('SELECT * FROM units').fetchall()
        conn.close()
        return [Unit.from_dict(unit) for unit in units]
    
    def save(self):
        """Gemmer eller opdaterer lejlighedsenheden i databasen"""
        conn = get_db_connection()
        now = datetime.now()
        
        if self.id is None:
            # Opret ny lejlighedsenhed
            self.id = str(uuid.uuid4())
            conn.execute('''
                INSERT INTO units (id, property_id, unit_number, floor, size, rooms, tenant_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (self.id, self.property_id, self.unit_number, self.floor, self.size, self.rooms, self.tenant_id, now, now))
        else:
            # Opdater eksisterende lejlighedsenhed
            self.updated_at = now
            conn.execute('''
                UPDATE units 
                SET property_id = ?, unit_number = ?, floor = ?, size = ?, rooms = ?, tenant_id = ?, updated_at = ?
                WHERE id = ?
            ''', (self.property_id, self.unit_number, self.floor, self.size, self.rooms, self.tenant_id, now, self.id))
        
        conn.commit()
        conn.close()
        return self.id
    
    def delete(self):
        """Sletter lejlighedsenheden fra databasen"""
        conn = get_db_connection()
        conn.execute('DELETE FROM units WHERE id = ?', (self.id,))
        conn.commit()
        conn.close()
        return True
    
    def to_dict(self):
        """Konverterer objektet til en dictionary"""
        return {
            'id': self.id,
            'property_id': self.property_id,
            'unit_number': self.unit_number,
            'floor': self.floor,
            'size': self.size,
            'rooms': self.rooms,
            'tenant_id': self.tenant_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def get_property(self):
        """Henter den tilhørende ejendom for denne lejlighedsenhed"""
        from app.models.property import Property
        return Property.get_by_id(self.property_id)
    
    def get_tenant(self):
        """Henter lejeren for denne lejlighedsenhed, hvis der er en"""
        if not self.tenant_id:
            return None
        from app.models.user import User
        return User.get_by_id(self.tenant_id)
    
    def get_tickets(self):
        """Henter alle tickets for denne lejlighedsenhed"""
        from app.models.ticket import Ticket
        conn = get_db_connection()
        tickets = conn.execute('SELECT * FROM tickets WHERE unit_id = ? ORDER BY created_at DESC', (self.id,)).fetchall()
        conn.close()
        from app.models.ticket import Ticket
        return [Ticket.from_dict(ticket) for ticket in tickets] 