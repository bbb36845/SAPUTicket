---
description:
globs:
---

# Your rule content
# SAPUTicket - Foreslået Projektstruktur

## Overordnet Arkitektur
For at forbedre projektets struktur, vedligeholdelse og skalerbarhed, foreslår jeg følgende omstrukturering:

```
SAPUTicket/
├── app/                      # Hovedapplikationskode
│   ├── __init__.py           # Initialisering af Flask-app
│   ├── config.py             # Konfigurationsindstillinger
│   ├── models/               # Database modeller
│   │   ├── __init__.py
│   │   ├── user.py           # Brugermodel
│   │   ├── property.py       # Ejendomsmodel
│   │   ├── unit.py           # Lejemålsmodel
│   │   ├── ticket.py         # Ticketmodel
│   │   └── message.py        # Beskedmodel (ny)
│   ├── routes/               # Route-håndtering
│   │   ├── __init__.py
│   │   ├── auth.py           # Autentificering
│   │   ├── admin.py          # Administrator routes
│   │   ├── landlord.py       # Udlejer routes
│   │   ├── tenant.py         # Lejer routes (ny)
│   │   ├── craftsman.py      # Håndværker routes
│   │   └── common.py         # Fælles routes
│   ├── services/             # Forretningslogik
│   │   ├── __init__.py
│   │   ├── auth_service.py   # Autentificeringslogik
│   │   ├── email_service.py  # Email notifikationer (ny)
│   │   ├── import_service.py # CSV import funktionalitet (ny)
│   │   ├── file_service.py   # Filhåndtering
│   │   └── invitation_service.py # Invitationssystem (ny)
│   ├── static/               # Statiske filer
│   │   ├── css/              # CSS-filer
│   │   │   ├── main.css      # Hovedstilark
│   │   │   ├── buttons.css   # Knap-styling
│   │   │   ├── forms.css     # Formular-styling
│   │   │   └── layout.css    # Layout-styling
│   │   ├── js/               # JavaScript-filer
│   │   │   ├── main.js       # Hovedscript
│   │   │   └── validation.js # Formularvalidering
│   │   ├── img/              # Billeder til UI
│   │   └── uploads/          # Uploadede filer
│   │       ├── images/       # Billeder
│   │       └── documents/    # Dokumenter (ny)
│   └── templates/            # HTML skabeloner
│       ├── base.html         # Grundlæggende skabelon
│       ├── components/       # Genbrugelige komponenter
│       │   ├── navbar.html   # Navigation
│       │   ├── footer.html   # Sidefod
│       │   ├── buttons.html  # Knapper
│       │   └── forms.html    # Formularer
│       ├── admin/            # Administrator sider
│       ├── landlord/         # Udlejer sider
│       ├── tenant/           # Lejer sider (ny)
│       ├── craftsman/        # Håndværker sider
│       ├── auth/             # Login/registrering
│       └── landing/          # Landingssider (ny)
├── migrations/               # Database migrationer
├── tests/                    # Testfiler
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_routes.py
│   └── test_services.py
├── .env                      # Miljøvariabler
├── .gitignore                # Git ignore fil
├── requirements.txt          # Afhængigheder
├── run.py                    # Applikationsindgangspunkt
└── README.md                 # Projektdokumentation
```

## Modulopdeling af app.py
Den nuværende app.py fil (161 KB) bør opdeles i mindre, mere håndterbare moduler:

1. **app/__init__.py**: Initialisering af Flask-app, registrering af blueprints
2. **app/config.py**: Konfigurationsindstillinger, miljøvariabler
3. **app/models/**: Database modeller for hver entitet
4. **app/routes/**: Route-håndtering opdelt efter brugertype
5. **app/services/**: Forretningslogik og eksterne integrationer

## CSS Organisering
For at løse problemet med blandet styling:

1. **Centraliseret CSS**: Alle stilarter samles i dedikerede CSS-filer
2. **Komponentbaseret tilgang**: Genbrugelige komponenter som knapper, formularer, osv.
3. **Variabel-definitioner**: Farver, skygger, og andre designvariable defineres ét sted
4. **Konsistent navngivning**: Ensartet navngivningskonvention for alle CSS-klasser

## Database Udvidelser
For at understøtte de nye funktioner, skal databasen udvides med:

1. **messages**: Tabel til beskedsystem mellem brugere
   - id, sender_id, receiver_id, message, timestamp, read

2. **files**: Tabel til filvedhæftninger
   - id, ticket_id, filename, path, upload_date, uploader_id

3. **notifications**: Tabel til notifikationer
   - id, user_id, message, type, timestamp, read

4. **invitations**: Tabel til invitationer (kan være en del af users-tabellen)
   - id, email, token, expiry_date, unit_id

## Nye Funktionaliteter
Implementering af de manglende funktioner:

1. **Lejer Portal**:
   - Login/registrering for lejere
   - Oversigt over egne tickets
   - Oprettelse af nye tickets
   - Kommunikation med udlejer/administrator

2. **Import Funktionalitet**:
   - CSV-import af ejendomme, lejemål og lejere
   - Validering og fejlhåndtering
   - Statusrapportering af import

3. **Notifikationssystem**:
   - Email-notifikationer via SendGrid
   - Notifikationer ved ændringer i tickets
   - Notifikationer ved nye beskeder
   - Notifikationer ved nye filupload

4. **Udvidet Håndværkerfunktionalitet**:
   - Upload af tilbudsfiler
   - Bedre visning af tilbud for udlejer/administrator

5. **Filvedhæftningssystem**:
   - Upload af filer til tickets
   - Visning af filer baseret på brugerrolle

6. **Beskedsystem**:
   - Direkte kommunikation mellem brugere
   - Beskedhistorik og notifikationer

7. **Invitationssystem**:
   - Generering af invitationslinks til lejere
   - Registreringsflow for inviterede brugere

8. **Frontend Landing Page**:
   - Hero-sektion med produktbeskrivelse
   - Kontaktformular
   - Feature-oversigt
   - Priser og tilmeldingsmulighed

