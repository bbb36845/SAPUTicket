import uuid
from datetime import datetime
from app.db import get_db_connection

class Property:
    """Klasse der repræsenterer en ejendom"""
    
    def __init__(self, id=None, name=None, address=None, zip_code=None, city=None, 
                 landlord_id=None, created_at=None, updated_at=None):
        """Initialiserer et Property objekt"""
        self.id = id
        self.name = name
        self.address = address
        self.zip_code = zip_code
        self.city = city
        self.landlord_id = landlord_id
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
    
    @staticmethod
    def from_dict(property_dict):
        """Opretter et Property objekt fra en dictionary (typisk fra databasen)"""
        if not property_dict:
            return None
        return Property(
            id=property_dict['id'],
            name=property_dict['name'],
            address=property_dict['address'],
            zip_code=property_dict['zip_code'],
            city=property_dict['city'],
            landlord_id=property_dict['landlord_id'],
            created_at=property_dict.get('created_at'),
            updated_at=property_dict.get('updated_at')
        )
    
    @staticmethod
    def get_by_id(property_id):
        """Henter en ejendom fra databasen baseret på ID"""
        conn = get_db_connection()
        property_data = conn.execute('SELECT * FROM properties WHERE id = ?', (property_id,)).fetchone()
        conn.close()
        return Property.from_dict(property_data) if property_data else None
    
    @staticmethod
    def get_by_landlord(landlord_id):
        """Henter alle ejendomme for en bestemt udlejer"""
        conn = get_db_connection()
        properties = conn.execute('SELECT * FROM properties WHERE landlord_id = ?', (landlord_id,)).fetchall()
        conn.close()
        return [Property.from_dict(prop) for prop in properties]
    
    @staticmethod
    def get_all():
        """Henter alle ejendomme fra databasen"""
        conn = get_db_connection()
        properties = conn.execute('SELECT * FROM properties').fetchall()
        conn.close()
        return [Property.from_dict(prop) for prop in properties]
    
    def save(self):
        """Gemmer eller opdaterer ejendommen i databasen"""
        conn = get_db_connection()
        now = datetime.now()
        
        if self.id is None:
            # Opret ny ejendom
            self.id = str(uuid.uuid4())
            conn.execute('''
                INSERT INTO properties (id, name, address, zip_code, city, landlord_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (self.id, self.name, self.address, self.zip_code, self.city, self.landlord_id, now, now))
        else:
            # Opdater eksisterende ejendom
            self.updated_at = now
            conn.execute('''
                UPDATE properties 
                SET name = ?, address = ?, zip_code = ?, city = ?, landlord_id = ?, updated_at = ?
                WHERE id = ?
            ''', (self.name, self.address, self.zip_code, self.city, self.landlord_id, now, self.id))
        
        conn.commit()
        conn.close()
        return self.id
    
    def delete(self):
        """Sletter ejendommen fra databasen"""
        conn = get_db_connection()
        conn.execute('DELETE FROM properties WHERE id = ?', (self.id,))
        conn.commit()
        conn.close()
        return True
    
    def to_dict(self):
        """Konverterer objektet til en dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'address': self.address,
            'zip_code': self.zip_code,
            'city': self.city,
            'landlord_id': self.landlord_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def get_units(self):
        """Henter alle lejligheder (units) for denne ejendom"""
        from app.models.unit import Unit
        return Unit.get_by_property(self.id) 