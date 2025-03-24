# Import af blueprints
# Disse vil blive defineret i deres respektive filer og importeret her
# for at gøre dem tilgængelige for app/__init__.py

# Bemærk: Blueprints skal defineres i deres respektive filer først,
# før de kan importeres her.

from app.routes.auth import auth_bp
from app.routes.admin import admin_bp
from app.routes.landlord import landlord_bp
from app.routes.tenant import tenant_bp
from app.routes.craftsman import craftsman_bp
from app.routes.common import common_bp
