import os
import uuid
from PIL import Image
from io import BytesIO
from werkzeug.utils import secure_filename
import sqlite3

# Konfiguration for billedupload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """
    Kontrollerer om filtypen er tilladt.
    
    Args:
        filename: Filnavnet der skal kontrolleres
        
    Returns:
        True hvis filtypen er tilladt, False ellers
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_image(stream):
    """
    Validerer at filen faktisk er et billede ved hjælp af PIL i stedet for imghdr.
    
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

def save_image(file, ticket_id, user_id, app_config, add_ticket_history_func, get_db_connection_func):
    """
    Gemmer et uploadet billede og tilføjer det til databasen.
    
    Args:
        file: Det uploadede fil-objekt
        ticket_id: ID på den ticket, billedet vedrører
        user_id: ID på den bruger, der uploader billedet
        app_config: Flask app konfiguration
        add_ticket_history_func: Funktion til at tilføje ticket-historik
        get_db_connection_func: Funktion til at få databaseforbindelse
        
    Returns:
        ID på det gemte billede hvis det blev gemt, None ellers
    """
    try:
        # Valider filnavn og filtype
        if file and allowed_file(file.filename):
            # Sikre filnavnet
            original_filename = secure_filename(file.filename)
            
            # Generer et unikt filnavn
            file_ext = os.path.splitext(original_filename)[1]
            unique_filename = str(uuid.uuid4()) + file_ext
            
            # Opret sti til filen
            file_path = os.path.join(app_config['UPLOAD_FOLDER'], unique_filename)
            
            # Gem filen
            file.save(file_path)
            
            # Få filstørrelse
            file_size = os.path.getsize(file_path)
            
            # Få MIME-type
            mime_type = file.content_type if hasattr(file, 'content_type') else 'image/jpeg'
            
            # Gem information i databasen
            conn = get_db_connection_func()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO ticket_images 
                (ticket_id, user_id, filename, original_filename, file_path, file_size, mime_type) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (ticket_id, user_id, unique_filename, original_filename, file_path, file_size, mime_type)
            )
            image_id = cursor.lastrowid
            
            # Tilføj handling til ticket-historikken
            add_ticket_history_func(ticket_id, user_id, 'image_added', None, original_filename, existing_conn=conn)
            
            conn.commit()
            conn.close()
            
            return image_id
        return None
    except Exception as e:
        print(f"Fejl ved gemning af billede: {e}")
        return None

def get_ticket_images(ticket_id, get_db_connection_func):
    """
    Henter alle billeder tilknyttet en ticket.
    
    Args:
        ticket_id: ID på den ticket, hvis billeder skal hentes
        get_db_connection_func: Funktion til at få databaseforbindelse
        
    Returns:
        Liste af billeder tilknyttet ticketen
    """
    try:
        conn = get_db_connection_func()
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

def delete_image(image_id, user_id, get_db_connection_func, add_ticket_history_func):
    """
    Sletter et billede fra databasen og filsystemet.
    
    Args:
        image_id: ID på det billede, der skal slettes
        user_id: ID på den bruger, der forsøger at slette billedet
        get_db_connection_func: Funktion til at få databaseforbindelse
        add_ticket_history_func: Funktion til at tilføje ticket-historik
        
    Returns:
        True hvis billedet blev slettet, False ellers
    """
    try:
        conn = get_db_connection_func()
        
        # Hent billedinformation
        image = conn.execute("SELECT * FROM ticket_images WHERE id = ?", (image_id,)).fetchone()
        
        if not image:
            conn.close()
            return False
        
        # Hent brugerrolle
        user = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
        
        # Kontroller om brugeren har tilladelse til at slette billedet
        if user['role'] not in ['admin', 'udlejer']:
            conn.close()
            return False
        
        # Slet filen fra filsystemet
        try:
            os.remove(image['file_path'])
        except OSError:
            # Fortsæt selvom filen ikke kunne slettes fra filsystemet
            pass
        
        # Tilføj handling til ticket-historikken
        add_ticket_history_func(image['ticket_id'], user_id, 'image_deleted', image['original_filename'], None, existing_conn=conn)
        
        # Slet billedet fra databasen
        conn.execute("DELETE FROM ticket_images WHERE id = ?", (image_id,))
        
        conn.commit()
        conn.close()
        
        return True
    except Exception as e:
        print(f"Fejl ved sletning af billede: {e}")
        return False 