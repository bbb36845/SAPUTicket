import sqlite3
import uuid
import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.db import get_db_connection

class User(UserMixin):
    """Klasse der repræsenterer en bruger i systemet"""
    
    def __init__(self, id=None, username=None, password_hash=None, role=None, 
                 invitation_token=None, invited_by=None, unit_id=None, email=None,
                 phone=None, company_name=None, speciality=None, created_at=None, 
                 updated_at=None, invitation_expires_at=None, is_active=True,
                 reset_token=None, reset_token_expires_at=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.invitation_token = invitation_token
        self.invited_by = invited_by
        self.unit_id = unit_id
        self.email = email
        self.phone = phone
        self.company_name = company_name
        self.speciality = speciality
        self.created_at = created_at or datetime.datetime.now()
        self.updated_at = updated_at or datetime.datetime.now()
        self.invitation_expires_at = invitation_expires_at
        self.is_active = is_active
        self.reset_token = reset_token
        self.reset_token_expires_at = reset_token_expires_at

    @staticmethod
    def get_by_id(user_id):
        """Henter en bruger baseret på ID"""
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        
        if not user:
            return None
        
        return User.from_dict(user)

    @staticmethod
    def get_by_username(username):
        """Henter en bruger baseret på brugernavn"""
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if not user:
            return None
        
        return User.from_dict(user)

    @staticmethod
    def from_dict(user_dict):
        """Opretter et User objekt fra en dictionary (typisk fra databasen)"""
        if not user_dict:
            return None
            
        return User(
            id=user_dict['id'],
            username=user_dict['username'],
            password_hash=user_dict['password_hash'],
            role=user_dict['role'],
            invitation_token=user_dict.get('invitation_token'),
            invited_by=user_dict.get('invited_by'),
            unit_id=user_dict.get('unit_id'),
            email=user_dict.get('email'),
            phone=user_dict.get('phone'),
            company_name=user_dict.get('company_name'),
            speciality=user_dict.get('speciality'),
            created_at=user_dict.get('created_at'),
            updated_at=user_dict.get('updated_at'),
            invitation_expires_at=user_dict.get('invitation_expires_at'),
            is_active=user_dict.get('is_active', 1) == 1,
            reset_token=user_dict.get('reset_token'),
            reset_token_expires_at=user_dict.get('reset_token_expires_at')
        )

    @staticmethod
    def create(username, password, role, unit_id=None, email=None, phone=None, 
               company_name=None, speciality=None, invited_by=None):
        """Opretter en ny bruger i databasen"""
        conn = get_db_connection()
        
        # Generer et unikt bruger-id
        user_id = str(uuid.uuid4())
        
        # Hash kodeordet til sikker lagring
        password_hash = generate_password_hash(password)
        
        # Indsæt bruger i databasen
        now = datetime.datetime.now()
        
        conn.execute('''
            INSERT INTO users
            (id, username, password_hash, role, unit_id, email, phone, company_name, speciality, 
             invited_by, created_at, updated_at, is_active) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, password_hash, role, unit_id, email, phone, 
              company_name, speciality, invited_by, now, now, 1))
        
        conn.commit()
        conn.close()
        
        return user_id

    def update(self, username=None, role=None, unit_id=None, email=None, phone=None, 
               company_name=None, speciality=None):
        """Opdaterer en eksisterende brugers information"""
        if not self.id:
            return False
            
        conn = get_db_connection()
        
        # Opdater brugeren i databasen
        self.username = username or self.username
        self.role = role or self.role
        self.unit_id = unit_id if unit_id is not None else self.unit_id
        self.email = email or self.email
        self.phone = phone or self.phone
        self.company_name = company_name or self.company_name
        self.speciality = speciality or self.speciality
        self.updated_at = datetime.datetime.now()
        
        conn.execute('''
            UPDATE users
            SET username = ?, role = ?, unit_id = ?, email = ?, phone = ?, 
                company_name = ?, speciality = ?, updated_at = ?
            WHERE id = ?
        ''', (self.username, self.role, self.unit_id, self.email, self.phone, 
              self.company_name, self.speciality, self.updated_at, self.id))
        
        conn.commit()
        conn.close()
        
        return True

    def delete(self):
        """Sletter brugeren fra databasen"""
        if not self.id:
            return False
            
        conn = get_db_connection()
        conn.execute('DELETE FROM users WHERE id = ?', (self.id,))
        conn.commit()
        conn.close()
        
        return True

    def check_password(self, password):
        """Tjekker om det angivne kodeord matcher hash'et"""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def set_password(self, password):
        """Sætter et nyt kodeord for brugeren"""
        self.password_hash = generate_password_hash(password)
        
        conn = get_db_connection()
        conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', 
                   (self.password_hash, self.id))
        conn.commit()
        conn.close()
        
        return True

    def generate_invitation_token(self, expiration_days=7):
        """Genererer et invitationstoken til brugeren"""
        self.invitation_token = str(uuid.uuid4())
        self.invitation_expires_at = datetime.datetime.now() + datetime.timedelta(days=expiration_days)
        
        conn = get_db_connection()
        conn.execute('''
            UPDATE users 
            SET invitation_token = ?, invitation_expires_at = ? 
            WHERE id = ?
        ''', (self.invitation_token, self.invitation_expires_at, self.id))
        conn.commit()
        conn.close()
        
        return self.invitation_token
        
    def generate_reset_token(self, expiration_hours=24):
        """Genererer et reset token til nulstilling af kodeord"""
        self.reset_token = str(uuid.uuid4())
        self.reset_token_expires_at = datetime.datetime.now() + datetime.timedelta(hours=expiration_hours)
        
        conn = get_db_connection()
        conn.execute('''
            UPDATE users 
            SET reset_token = ?, reset_token_expires_at = ? 
            WHERE id = ?
        ''', (self.reset_token, self.reset_token_expires_at, self.id))
        conn.commit()
        conn.close()
        
        return self.reset_token

# Hjælpefunktioner for brugerrelaterede operationer
def get_all_users():
    """Henter alle brugere fra databasen"""
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    
    return [User.from_dict(user) for user in users]

def get_users_by_unit(unit_id):
    """Henter alle brugere tilknyttet en bestemt lejlighedsenhed"""
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users WHERE unit_id = ?', (unit_id,)).fetchall()
    conn.close()
    
    return [User.from_dict(user) for user in users]

def get_user_by_invitation_token(token):
    """Henter en bruger baseret på invitationstoken"""
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE invitation_token = ?', (token,)).fetchone()
    conn.close()
    
    if not user:
        return None
    
    # Opret et User-objekt fra resultatet
    user_obj = User.from_dict(user)
    
    # Tjek om invitationen er udløbet
    if user_obj.invitation_expires_at and user_obj.invitation_expires_at < datetime.datetime.now():
        return None
    
    return user_obj

def get_user_by_reset_token(token):
    """Henter en bruger baseret på reset token til nulstilling af kodeord"""
    conn = get_db_connection()
    user = conn.execute('''
        SELECT * FROM users 
        WHERE reset_token = ? AND reset_token_expires_at > ?
    ''', (token, datetime.datetime.now())).fetchone()
    conn.close()
    
    if not user:
        return None
    
    return User.from_dict(user) 