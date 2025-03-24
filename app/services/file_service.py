import os
import uuid
from PIL import Image
from io import BytesIO
from werkzeug.utils import secure_filename
import sqlite3
from datetime import datetime

from app.config import get_config

config = get_config()

def get_db_connection():
    """Opretter en forbindelse til databasen."""
    conn = sqlite3.connect(config.DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def allowed_image_file(filename):
    """
    Kontrollerer om filtypen er en tilladt billedtype.
    
    Args:
        filename: Filnavnet der skal kontrolleres
        
    Returns:
        True hvis filtypen er tilladt, False ellers
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config.ALLOWED_IMAGE_EXTENSIONS

def allowed_document_file(filename):
    """
    Kontrollerer om filtypen er en tilladt dokumenttype.
    
    Args:
        filename: Filnavnet der skal kontrolleres
        
    Returns:
        True hvis filtypen er tilladt, False ellers
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config.ALLOWED_DOCUMENT_EXTENSIONS

def validate_image(stream):
    """
    Validerer at filen faktisk er et billede ved hjælp af PIL.
    
    Args:
        stream: Filstrømmen der skal valideres
        
    Returns:
        Filtypen hvis det er et gyldigt billede, None ellers
    """
    try:
        # Læs de første bytes af filen
        header = stream.read(512)
        stream.seek(0)
        
        # Brug PIL til at identificere billedformat
        img = Image.open(BytesIO(header))
        format = img.format.lower()
        
        if not format:
            return None
        
        # PIL returnerer 'jpeg' for jpg-filer, så vi konverterer til .jpg extension
        if format == 'jpeg':
            return '.jpg'
        return '.' + format
    except Exception:
        return None

def save_image(file, ticket_id, user_id, add_ticket_history=None):
    """
    Gemmer et uploadet billede og tilføjer det til databasen.
    
    Args:
        file: Det uploadede fil-objekt
        ticket_id: ID på den ticket, billedet vedrører
        user_id: ID på den bruger, der uploader billedet
        add_ticket_history: Funktion til at tilføje ticket-historik
        
    Returns:
        ID på det gemte billede hvis det blev gemt, None ellers
    """
    try:
        # Valider filnavn og filtype
        if file and allowed_image_file(file.filename):
            # Sikre filnavnet
            original_filename = secure_filename(file.filename)
            
            # Generer et unikt filnavn
            file_ext = os.path.splitext(original_filename)[1]
            unique_filename = str(uuid.uuid4()) + file_ext
            
            # Opret sti til filen
            file_path = os.path.join(config.IMAGES_FOLDER, unique_filename)
            
            # Gem filen
            file.save(file_path)
            
            # Få filstørrelse
            file_size = os.path.getsize(file_path)
            
            # Få MIME-type
            mime_type = file.content_type if hasattr(file, 'content_type') else 'image/jpeg'
            
            # Gem information i databasen
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO ticket_images 
                (ticket_id, user_id, filename, original_filename, file_path, file_size, mime_type, created_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ticket_id, user_id, unique_filename, original_filename, file_path, file_size, mime_type, datetime.now())
            )
            image_id = cursor.lastrowid
            
            # Tilføj handling til ticket-historikken
            if add_ticket_history:
                add_ticket_history(ticket_id, user_id, 'image_added', None, original_filename, existing_conn=conn)
            
            conn.commit()
            conn.close()
            
            return image_id
        return None
    except Exception as e:
        print(f"Fejl ved gemning af billede: {e}")
        return None

def save_document(file, ticket_id, user_id, add_ticket_history=None):
    """
    Gemmer et uploadet dokument og tilføjer det til databasen.
    
    Args:
        file: Det uploadede fil-objekt
        ticket_id: ID på den ticket, dokumentet vedrører
        user_id: ID på den bruger, der uploader dokumentet
        add_ticket_history: Funktion til at tilføje ticket-historik
        
    Returns:
        ID på det gemte dokument hvis det blev gemt, None ellers
    """
    try:
        # Valider filnavn og filtype
        if file and allowed_document_file(file.filename):
            # Sikre filnavnet
            original_filename = secure_filename(file.filename)
            
            # Generer et unikt filnavn
            file_ext = os.path.splitext(original_filename)[1]
            unique_filename = str(uuid.uuid4()) + file_ext
            
            # Opret sti til filen
            file_path = os.path.join(config.DOCUMENTS_FOLDER, unique_filename)
            
            # Gem filen
            file.save(file_path)
            
            # Få filstørrelse
            file_size = os.path.getsize(file_path)
            
            # Få MIME-type
            mime_type = file.content_type if hasattr(file, 'content_type') else 'application/octet-stream'
            
            # Gem information i databasen (antager at vi har en ticket_documents tabel)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO ticket_documents 
                (ticket_id, user_id, filename, original_filename, file_path, file_size, mime_type, created_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ticket_id, user_id, unique_filename, original_filename, file_path, file_size, mime_type, datetime.now())
            )
            document_id = cursor.lastrowid
            
            # Tilføj handling til ticket-historikken
            if add_ticket_history:
                add_ticket_history(ticket_id, user_id, 'document_added', None, original_filename, existing_conn=conn)
            
            conn.commit()
            conn.close()
            
            return document_id
        return None
    except Exception as e:
        print(f"Fejl ved gemning af dokument: {e}")
        return None

def get_ticket_images(ticket_id):
    """
    Henter alle billeder tilknyttet en ticket.
    
    Args:
        ticket_id: ID på den ticket, hvis billeder skal hentes
        
    Returns:
        Liste af billeder tilknyttet ticketen
    """
    try:
        conn = get_db_connection()
        images = conn.execute(
            """
            SELECT i.*, u.username 
            FROM ticket_images i
            JOIN users u ON i.user_id = u.id
            WHERE i.ticket_id = ?
            ORDER BY i.created_at DESC
            """,
            (ticket_id,)
        ).fetchall()
        conn.close()
        return images
    except Exception as e:
        print(f"Fejl ved hentning af billeder: {e}")
        return []

def get_ticket_documents(ticket_id):
    """
    Henter alle dokumenter tilknyttet en ticket.
    
    Args:
        ticket_id: ID på den ticket, hvis dokumenter skal hentes
        
    Returns:
        Liste af dokumenter tilknyttet ticketen
    """
    try:
        conn = get_db_connection()
        documents = conn.execute(
            """
            SELECT d.*, u.username 
            FROM ticket_documents d
            JOIN users u ON d.user_id = u.id
            WHERE d.ticket_id = ?
            ORDER BY d.created_at DESC
            """,
            (ticket_id,)
        ).fetchall()
        conn.close()
        return documents
    except Exception as e:
        print(f"Fejl ved hentning af dokumenter: {e}")
        return []

def delete_file(file_id, file_type, user_id, add_ticket_history=None):
    """
    Sletter en fil (billede eller dokument) fra databasen og filsystemet.
    
    Args:
        file_id: ID på den fil, der skal slettes
        file_type: Type af fil ('image' eller 'document')
        user_id: ID på den bruger, der forsøger at slette filen
        add_ticket_history: Funktion til at tilføje ticket-historik
        
    Returns:
        True hvis filen blev slettet, False ellers
    """
    try:
        conn = get_db_connection()
        
        # Vælg tabel og hent filinformation
        if file_type == 'image':
            table_name = 'ticket_images'
            file = conn.execute(f"SELECT * FROM {table_name} WHERE id = ?", (file_id,)).fetchone()
        elif file_type == 'document':
            table_name = 'ticket_documents'
            file = conn.execute(f"SELECT * FROM {table_name} WHERE id = ?", (file_id,)).fetchone()
        else:
            conn.close()
            return False
        
        if not file:
            conn.close()
            return False
        
        # Hent brugerrolle
        user = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
        
        # Kontroller om brugeren har tilladelse til at slette filen
        if user['role'] not in ['admin', 'udlejer'] and user_id != file['user_id']:
            conn.close()
            return False
        
        # Slet filen fra filsystemet
        try:
            os.remove(file['file_path'])
        except OSError:
            # Fortsæt selvom filen ikke kunne slettes fra filsystemet
            pass
        
        # Tilføj handling til ticket-historikken
        if add_ticket_history:
            action_type = 'image_deleted' if file_type == 'image' else 'document_deleted'
            add_ticket_history(file['ticket_id'], user_id, action_type, file['original_filename'], None, existing_conn=conn)
        
        # Slet filen fra databasen
        conn.execute(f"DELETE FROM {table_name} WHERE id = ?", (file_id,))
        
        conn.commit()
        conn.close()
        
        return True
    except Exception as e:
        print(f"Fejl ved sletning af fil: {e}")
        return False 