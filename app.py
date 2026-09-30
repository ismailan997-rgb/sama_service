import os
import secrets
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
USE_POSTGRES = DATABASE_URL.startswith(('postgres://', 'postgresql://'))
DATABASE = os.environ.get('DATABASE_PATH', 'samaservice.db')
DEMO_ARTISAN_TELEPHONE = '771234567'
DEMO_SERVICE_TITLES = (
    'Diagnostic & Vidange Rapide Scooter / Moto',
    'Dépannage Mécanique Auto & Batterie',
)

if USE_POSTGRES:
    import psycopg
    from psycopg.rows import dict_row

    INTEGRITY_ERRORS = (psycopg.IntegrityError,)
else:
    INTEGRITY_ERRORS = (sqlite3.IntegrityError,)

app = Flask(__name__)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        'CORS_ORIGINS',
        'capacitor://localhost,http://localhost,https://localhost'
    ).split(',')
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": CORS_ORIGINS}})
MAX_PROFILE_PHOTO_BYTES = 5 * 1024 * 1024
ALLOWED_PROFILE_PHOTO_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
app.config['MAX_CONTENT_LENGTH'] = MAX_PROFILE_PHOTO_BYTES + 64 * 1024
profile_photo_serializer = URLSafeTimedSerializer(
    os.environ.get('FLASK_SECRET_KEY') or secrets.token_urlsafe(48),
    salt='samaservice-profile-photo'
)


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"success": False, "message": "La photo ne doit pas dépasser 5 Mo."}), 413


def cloudinary_credentials_configured():
    if os.environ.get('CLOUDINARY_URL', '').strip():
        return True
    return all(os.environ.get(key, '').strip() for key in (
        'CLOUDINARY_CLOUD_NAME',
        'CLOUDINARY_API_KEY',
        'CLOUDINARY_API_SECRET'
    ))


def get_cloudinary_uploader():
    if not cloudinary_credentials_configured():
        return None

    import cloudinary
    import cloudinary.uploader

    cloudinary_url = os.environ.get('CLOUDINARY_URL', '').strip()
    if cloudinary_url:
        cloudinary.config(cloudinary_url=cloudinary_url, secure=True)
    else:
        cloudinary.config(
            cloud_name=os.environ['CLOUDINARY_CLOUD_NAME'].strip(),
            api_key=os.environ['CLOUDINARY_API_KEY'].strip(),
            api_secret=os.environ['CLOUDINARY_API_SECRET'].strip(),
            secure=True
        )
    return cloudinary.uploader


def create_artisan_token(artisan_id):
    return profile_photo_serializer.dumps({"artisan_id": int(artisan_id)})


def get_authenticated_artisan_id():
    authorization = request.headers.get('Authorization', '')
    if not authorization.startswith('Bearer '):
        return None

    try:
        token_data = profile_photo_serializer.loads(
            authorization.removeprefix('Bearer '),
            max_age=60 * 60 * 24 * 30
        )
        return int(token_data['artisan_id'])
    except (BadSignature, KeyError, TypeError, ValueError):
        return None


def upload_profile_photo(photo):
    if photo is None or not photo.filename:
        return None, "Choisissez une photo à envoyer."
    if photo.mimetype not in ALLOWED_PROFILE_PHOTO_TYPES:
        return None, "Format invalide. Choisissez une image JPEG, PNG ou WebP."

    uploader = get_cloudinary_uploader()
    if uploader is None:
        return None, "Le stockage photo n'est pas configuré. Contactez l'administrateur."

    try:
        result = uploader.upload(
            photo.stream,
            folder='samaservice/profiles',
            resource_type='image',
            allowed_formats=['jpg', 'jpeg', 'png', 'webp'],
            transformation=[{
                'width': 512,
                'height': 512,
                'crop': 'fill',
                'gravity': 'auto',
                'quality': 'auto',
                'fetch_format': 'auto'
            }]
        )
    except Exception:
        app.logger.exception("Échec du téléversement Cloudinary")
        return None, "La photo n'a pas pu être envoyée. Réessayez plus tard."

    if not result.get('secure_url') or not result.get('public_id'):
        return None, "Cloudinary n'a pas retourné les informations de la photo."
    return result, None


def delete_cloudinary_photo(public_id):
    if not public_id:
        return True

    uploader = get_cloudinary_uploader()
    if uploader is None:
        return False

    try:
        uploader.destroy(public_id, resource_type='image', invalidate=True)
        return True
    except Exception:
        app.logger.exception("Échec de la suppression Cloudinary")
        return False

# Liste des quartiers populaires de Dakar
QUARTIERS_DAKAR = [
    "Almadies", "Ngor", "Ouakam", "Yoff", "Mermoz", "Sacré-Cœur", 
    "Fann - Point E", "Médina", "Dakar-Plateau", "Grand Dakar",
    "Liberté 1-6", "Dieuppeul - Derklé", "Hann Maristes", "Grand Yoff",
    "Parcelles Assainies", "Pikine", "Guédiawaye", "Keur Massar", "Rufisque"
]

METIERS_LISTE = [
    {"id": "mecanicien", "nom": "Mécanicien Auto / Moto", "icone": "fa-wrench", "emoji": "🚗"},
    {"id": "vulcanisateur", "nom": "Vulcanisateur / dépannage pneus", "icone": "fa-car-burst", "emoji": "🛞"},
    {"id": "plombier", "nom": "Plombier", "icone": "fa-faucet", "emoji": "🚰"},
    {"id": "electricien", "nom": "Électricien", "icone": "fa-bolt", "emoji": "⚡"},
    {"id": "climatisation", "nom": "Climatisation / Froid", "icone": "fa-snowflake", "emoji": "❄️"},
    {"id": "videosurveillance", "nom": "Technicien vidéosurveillance / alarmes", "icone": "fa-video", "emoji": "📹"},
    {"id": "informatique", "nom": "Technicien informatique / réparation PC", "icone": "fa-laptop", "emoji": "💻"},
    {"id": "telephones", "nom": "Réparateur de téléphones", "icone": "fa-mobile-screen-button", "emoji": "📱"},
    {"id": "reseau_fibre", "nom": "Technicien réseau / fibre optique", "icone": "fa-network-wired", "emoji": "🌐"},
    {"id": "electromenager", "nom": "Réparateur électroménager", "icone": "fa-plug", "emoji": "🔌"},
    {"id": "antenniste", "nom": "Installateur antennes / paraboles", "icone": "fa-satellite-dish", "emoji": "📡"},
    {"id": "solaire", "nom": "Installateur solaire / panneaux photovoltaïques", "icone": "fa-solar-panel", "emoji": "☀️"},
    {"id": "groupes_pompes", "nom": "Réparateur pompes / groupes électrogènes", "icone": "fa-gears", "emoji": "⚙️"},
    {"id": "menuisier", "nom": "Menuisier Bois / Aluminium", "icone": "fa-hammer", "emoji": "🪚"},
    {"id": "serrurier", "nom": "Serrurier", "icone": "fa-key", "emoji": "🔑"},
    {"id": "soudeur", "nom": "Soudeur / métallier", "icone": "fa-industry", "emoji": "🧰"},
    {"id": "macon", "nom": "Maçon", "icone": "fa-trowel-bricks", "emoji": "🧱"},
    {"id": "carreleur", "nom": "Carreleur", "icone": "fa-border-all", "emoji": "🧩"},
    {"id": "peintre", "nom": "Peintre en Bâtiment", "icone": "fa-paint-roller", "emoji": "🎨"},
    {"id": "staffeur", "nom": "Plâtrier / staffeur", "icone": "fa-house", "emoji": "🏠"},
    {"id": "couvreur", "nom": "Couvreur / étancheur", "icone": "fa-house-chimney", "emoji": "🏡"},
    {"id": "vitrier", "nom": "Vitrier", "icone": "fa-window-maximize", "emoji": "🪟"},
    {"id": "nettoyage", "nom": "Nettoyage & Débouchage", "icone": "fa-broom", "emoji": "🧹"},
    {"id": "jardinier", "nom": "Jardinier / paysagiste", "icone": "fa-seedling", "emoji": "🌱"},
    {"id": "desinsectisation", "nom": "Désinsectisation / dératisation", "icone": "fa-bug", "emoji": "🐜"},
    {"id": "demenageur", "nom": "Déménageur", "icone": "fa-truck-moving", "emoji": "🚚"},
    {"id": "aide_menagere", "nom": "Aide ménagère / repassage", "icone": "fa-shirt", "emoji": "🧺"},
    {"id": "couturier", "nom": "Couturier / retouche", "icone": "fa-scissors", "emoji": "🧵"},
    {"id": "coiffeur", "nom": "Coiffeur à domicile", "icone": "fa-scissors", "emoji": "💇"},
    {"id": "tapissier", "nom": "Tapissier / réparation de meubles", "icone": "fa-couch", "emoji": "🛋️"},
    {"id": "bricoleur", "nom": "Bricoleur polyvalent", "icone": "fa-screwdriver-wrench", "emoji": "🪛"},
    {"id": "lavage_auto", "nom": "Lavage auto à domicile", "icone": "fa-car-side", "emoji": "🚙"},
    {"id": "autre", "nom": "Autre artisan / prestataire", "icone": "fa-ellipsis", "emoji": "🧑🏾‍🔧"}
]

class CompatibleCursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=()):
        if USE_POSTGRES:
            query = query.replace('?', '%s')
        self.cursor.execute(query, params)
        return self

    def executemany(self, query, params):
        if USE_POSTGRES:
            query = query.replace('?', '%s')
        self.cursor.executemany(query, params)
        return self

    def __getattr__(self, name):
        return getattr(self.cursor, name)


class CompatibleConnection:
    def __init__(self, connection):
        self.connection = connection

    def cursor(self):
        return CompatibleCursor(self.connection.cursor())

    def __getattr__(self, name):
        return getattr(self.connection, name)


def get_db_connection():
    if USE_POSTGRES:
        return CompatibleConnection(psycopg.connect(DATABASE_URL, row_factory=dict_row))

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return CompatibleConnection(conn)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    id_definition = 'BIGSERIAL PRIMARY KEY' if USE_POSTGRES else 'INTEGER PRIMARY KEY AUTOINCREMENT'
    foreign_key_type = 'BIGINT' if USE_POSTGRES else 'INTEGER'
    
    # Table des comptes artisans
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS artisans (
            id {id_definition},
            nom TEXT NOT NULL,
            telephone TEXT UNIQUE NOT NULL,
            mot_de_passe TEXT NOT NULL,
            metier TEXT NOT NULL,
            quartier TEXT NOT NULL,
            note REAL DEFAULT 5.0,
            photo_url TEXT,
            photo_public_id TEXT,
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Table des services publiés par les artisans
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS services (
            id {id_definition},
            artisan_id {foreign_key_type} NOT NULL,
            titre_service TEXT NOT NULL,
            description_service TEXT NOT NULL,
            tarif_indicatif TEXT,
            actif INTEGER DEFAULT 1,
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (artisan_id) REFERENCES artisans (id)
        )
    ''')
    
    # Table des demandes clients
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS demandes (
            id {id_definition},
            service_id {foreign_key_type} NOT NULL,
            nom_client TEXT NOT NULL,
            telephone_client TEXT NOT NULL,
            description_besoin TEXT NOT NULL,
            statut TEXT DEFAULT 'Nouveau',
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (service_id) REFERENCES services (id)
        )
    ''')
    
    # Migrations de colonnes si besoin
    if USE_POSTGRES:
        cursor.execute("ALTER TABLE demandes ADD COLUMN IF NOT EXISTS statut TEXT DEFAULT 'Nouveau'")
        cursor.execute("ALTER TABLE services ADD COLUMN IF NOT EXISTS actif INTEGER DEFAULT 1")
        cursor.execute("ALTER TABLE artisans ADD COLUMN IF NOT EXISTS note REAL DEFAULT 5.0")
        cursor.execute("ALTER TABLE artisans ADD COLUMN IF NOT EXISTS photo_url TEXT")
        cursor.execute("ALTER TABLE artisans ADD COLUMN IF NOT EXISTS photo_public_id TEXT")
    else:
        try:
            cursor.execute("ALTER TABLE demandes ADD COLUMN statut TEXT DEFAULT 'Nouveau'")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE services ADD COLUMN actif INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE artisans ADD COLUMN note REAL DEFAULT 5.0")
        except sqlite3.OperationalError:
            pass

        for column_name in ('photo_url', 'photo_public_id'):
            try:
                cursor.execute(f"ALTER TABLE artisans ADD COLUMN {column_name} TEXT")
            except sqlite3.OperationalError:
                pass
    
    conn.commit()

    cursor.execute('''
        UPDATE services
        SET actif = 0
        WHERE titre_service IN (?, ?)
          AND artisan_id IN (
              SELECT id FROM artisans WHERE telephone = ?
          )
    ''', (*DEMO_SERVICE_TITLES, DEMO_ARTISAN_TELEPHONE))
    conn.commit()

    conn.close()

init_db()

# --- ROUTES UTILITAIRES ---
@app.route('/api/metadonnees', methods=['GET'])
def get_metadonnees():
    return jsonify({
        "quartiers": QUARTIERS_DAKAR,
        "metiers": METIERS_LISTE
    })

# --- AUTHENTIFICATION ARTISAN ---
@app.route('/api/artisan/inscription', methods=['POST'])
def inscription_artisan():
    data = request.json or {}
    nom = data.get('nom', '').strip()
    telephone = data.get('telephone', '').strip().replace(' ', '')
    mot_de_passe = data.get('mot_de_passe', '')
    metier = data.get('metier', '').strip()
    quartier = data.get('quartier', '').strip()

    if not nom or not telephone or not mot_de_passe or not metier or not quartier:
        return jsonify({"success": False, "message": "Veuillez remplir tous les champs obligatoires."}), 400

    mdp_stocke = generate_password_hash(mot_de_passe)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO artisans (nom, telephone, mot_de_passe, metier, quartier, note)
            VALUES (?, ?, ?, ?, ?, 5.0)
            RETURNING id
        ''', (nom, telephone, mdp_stocke, metier, quartier))
        artisan_id = cursor.fetchone()['id']
        conn.commit()
        conn.close()
        return jsonify({
            "success": True,
            "message": "Votre compte artisan a été créé avec succès !",
            "artisan": {
                "id": artisan_id,
                "nom": nom,
                "telephone": telephone,
                "metier": metier,
                "quartier": quartier,
                "note": 5.0,
                "photo_url": None,
                "photo_token": create_artisan_token(artisan_id)
            }
        }), 201
    except INTEGRITY_ERRORS:
        conn.close()
        return jsonify({"success": False, "message": "Ce numéro de téléphone est déjà enregistré."}), 400

@app.route('/api/artisan/connexion', methods=['POST'])
def connexion_artisan():
    data = request.json or {}
    telephone = data.get('telephone', '').strip().replace(' ', '')
    mot_de_passe = data.get('mot_de_passe', '')

    conn = get_db_connection()
    cursor = conn.cursor()
    artisan = cursor.execute('''
        SELECT id, nom, telephone, mot_de_passe, metier, quartier, note, photo_url FROM artisans
        WHERE telephone = ?
    ''', (telephone,)).fetchone()
    
    if artisan:
        # Vérification avec hachage ou rétrocompatibilité mot de passe en clair
        mot_de_passe_db = artisan['mot_de_passe']
        valide = False
        if mot_de_passe_db.startswith(('scrypt:', 'pbkdf2:')):
            valide = check_password_hash(mot_de_passe_db, mot_de_passe)
        else:
            valide = (mot_de_passe_db == mot_de_passe)
            if valide:
                nouveau_hash = generate_password_hash(mot_de_passe)
                cursor.execute('UPDATE artisans SET mot_de_passe = ? WHERE id = ?', (nouveau_hash, artisan['id']))
                conn.commit()

        if valide:
            res_artisan = {
                "id": artisan["id"],
                "nom": artisan["nom"],
                "telephone": artisan["telephone"],
                "metier": artisan["metier"],
                "quartier": artisan["quartier"],
                "note": artisan["note"] if "note" in artisan.keys() else 5.0,
                "photo_url": artisan["photo_url"],
                "photo_token": create_artisan_token(artisan["id"])
            }
            conn.close()
            return jsonify({"success": True, "artisan": res_artisan})

    conn.close()
    return jsonify({"success": False, "message": "Numéro de téléphone ou mot de passe incorrect."}), 401


@app.route('/api/artisan/profil', methods=['PATCH'])
def modifier_profil_artisan():
    artisan_id = get_authenticated_artisan_id()
    if artisan_id is None:
        return jsonify({"success": False, "message": "Connectez-vous pour modifier votre profil."}), 401

    data = request.get_json(silent=True) or {}
    fields = ('nom', 'telephone', 'metier', 'quartier')
    if not all(isinstance(data.get(field), str) for field in fields):
        return jsonify({"success": False, "message": "Vérifiez les informations du profil."}), 400

    nom = data['nom'].strip()
    telephone = ''.join(data['telephone'].split())
    metier = data['metier'].strip()
    quartier = data['quartier'].strip()
    metiers_autorises = {metier['nom'] for metier in METIERS_LISTE}

    if not nom or len(nom) > 100 or not telephone or len(telephone) > 20:
        return jsonify({"success": False, "message": "Le nom ou le téléphone est invalide."}), 400
    if metier not in metiers_autorises or quartier not in QUARTIERS_DAKAR:
        return jsonify({"success": False, "message": "Choisissez un métier et un quartier valides."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE artisans
            SET nom = ?, telephone = ?, metier = ?, quartier = ?
            WHERE id = ?
        ''', (nom, telephone, metier, quartier, artisan_id))
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({"success": False, "message": "Compte artisan introuvable."}), 404
        conn.commit()
    except INTEGRITY_ERRORS:
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": "Ce numéro de téléphone est déjà utilisé."}), 409

    artisan = cursor.execute('''
        SELECT id, nom, telephone, metier, quartier, note, photo_url
        FROM artisans WHERE id = ?
    ''', (artisan_id,)).fetchone()
    conn.close()
    return jsonify({"success": True, "artisan": dict(artisan)})


@app.route('/api/artisan/photo', methods=['POST'])
def remplacer_photo_profil():
    artisan_id = get_authenticated_artisan_id()
    if artisan_id is None:
        return jsonify({"success": False, "message": "Reconnectez-vous pour modifier votre photo."}), 401

    photo = request.files.get('photo')
    if photo is None or not photo.filename:
        return jsonify({"success": False, "message": "Choisissez une photo à envoyer."}), 400
    if photo.mimetype not in ALLOWED_PROFILE_PHOTO_TYPES:
        return jsonify({"success": False, "message": "Choisissez une image JPEG, PNG ou WebP."}), 400
    if not cloudinary_credentials_configured():
        return jsonify({"success": False, "message": "Le stockage photo n'est pas configuré."}), 503

    conn = get_db_connection()
    cursor = conn.cursor()
    artisan = cursor.execute(
        'SELECT photo_public_id FROM artisans WHERE id = ?',
        (artisan_id,)
    ).fetchone()
    if not artisan:
        conn.close()
        return jsonify({"success": False, "message": "Compte artisan introuvable."}), 404

    result, error = upload_profile_photo(photo)
    if error:
        conn.close()
        return jsonify({"success": False, "message": error}), 502

    old_public_id = artisan['photo_public_id']
    try:
        cursor.execute(
            'UPDATE artisans SET photo_url = ?, photo_public_id = ? WHERE id = ?',
            (result['secure_url'], result['public_id'], artisan_id)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        delete_cloudinary_photo(result['public_id'])
        app.logger.exception("Échec de l'enregistrement de la photo de profil")
        return jsonify({"success": False, "message": "La photo n'a pas pu être enregistrée."}), 500
    conn.close()

    if old_public_id and old_public_id != result['public_id']:
        delete_cloudinary_photo(old_public_id)

    return jsonify({"success": True, "photo_url": result['secure_url']})


@app.route('/api/artisan/photo', methods=['DELETE'])
def supprimer_photo_profil():
    artisan_id = get_authenticated_artisan_id()
    if artisan_id is None:
        return jsonify({"success": False, "message": "Reconnectez-vous pour modifier votre photo."}), 401
    if not cloudinary_credentials_configured():
        return jsonify({"success": False, "message": "Le stockage photo n'est pas configuré."}), 503

    conn = get_db_connection()
    cursor = conn.cursor()
    artisan = cursor.execute(
        'SELECT photo_public_id FROM artisans WHERE id = ?',
        (artisan_id,)
    ).fetchone()
    if not artisan:
        conn.close()
        return jsonify({"success": False, "message": "Compte artisan introuvable."}), 404

    public_id = artisan['photo_public_id']
    cursor.execute(
        'UPDATE artisans SET photo_url = NULL, photo_public_id = NULL WHERE id = ?',
        (artisan_id,)
    )
    conn.commit()
    conn.close()

    if public_id:
        delete_cloudinary_photo(public_id)

    return jsonify({"success": True, "photo_url": None})

# --- SERVICES & DEMANDES ---
@app.route('/api/services', methods=['GET'])
def lister_services():
    metier = request.args.get('metier')
    quartier = request.args.get('quartier')
    q = request.args.get('q', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    query = '''
        SELECT s.*, a.nom as nom_artisan, a.telephone as telephone_artisan, a.metier, a.quartier, a.note 
        FROM services s
        JOIN artisans a ON s.artisan_id = a.id
        WHERE (s.actif IS NULL OR s.actif = 1)
    '''
    params = []

    if metier and metier != 'Tous':
        query += ' AND a.metier = ?'
        params.append(metier)

    if quartier and quartier != 'Tous':
        query += ' AND a.quartier = ?'
        params.append(quartier)

    if q:
        query += ' AND (s.titre_service LIKE ? OR s.description_service LIKE ? OR a.nom LIKE ?)'
        wildcard = f"%{q}%"
        params.extend([wildcard, wildcard, wildcard])

    query += ' ORDER BY s.date_creation DESC'
    services = cursor.execute(query, params).fetchall()
    conn.close()

    return jsonify({"success": True, "data": [dict(s) for s in services]})

@app.route('/api/services', methods=['POST'])
def publier_service():
    data = request.json or {}
    artisan_id = get_authenticated_artisan_id()
    titre = data.get('titre_service', '').strip()
    description = data.get('description_service', '').strip()
    tarif = data.get('tarif_indicatif', '').strip() or 'Sur devis'

    if artisan_id is None:
        return jsonify({"success": False, "message": "Reconnectez-vous pour publier un service."}), 401
    if not titre or not description:
        return jsonify({"success": False, "message": "Titre et description obligatoires."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO services (artisan_id, titre_service, description_service, tarif_indicatif, actif)
        VALUES (?, ?, ?, ?, 1)
    ''', (artisan_id, titre, description, tarif))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Service publié dans l'application !"}), 201

@app.route('/api/services/<int:service_id>', methods=['DELETE'])
def supprimer_service(service_id):
    artisan_id = get_authenticated_artisan_id()
    if artisan_id is None:
        return jsonify({"success": False, "message": "Reconnectez-vous pour retirer un service."}), 401

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE services SET actif = 0 WHERE id = ? AND artisan_id = ?',
        (service_id, artisan_id)
    )
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"success": False, "message": "Service introuvable."}), 404
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Service retiré."})

@app.route('/api/demandes', methods=['POST'])
def envoyer_demande():
    data = request.json or {}
    service_id = data.get('service_id')
    nom_client = data.get('nom_client', '').strip()
    telephone_client = data.get('telephone_client', '').strip().replace(' ', '')
    description = data.get('description_besoin', '').strip()

    if not service_id or not nom_client or not telephone_client or not description:
        return jsonify({"success": False, "message": "Tous les champs de la demande sont requis."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    service = cursor.execute(
        'SELECT id FROM services WHERE id = ? AND (actif IS NULL OR actif = 1)',
        (service_id,)
    ).fetchone()
    if not service:
        conn.close()
        return jsonify({"success": False, "message": "Cette prestation n'est plus disponible."}), 404

    cursor.execute('''
        INSERT INTO demandes (service_id, nom_client, telephone_client, description_besoin, statut)
        VALUES (?, ?, ?, ?, 'Nouveau')
    ''', (service_id, nom_client, telephone_client, description))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Votre demande a été envoyée à l'artisan !"}), 201

@app.route('/api/artisan/<int:artisan_id>/demandes', methods=['GET'])
def mes_demandes(artisan_id):
    authenticated_id = get_authenticated_artisan_id()
    if authenticated_id is None:
        return jsonify({"success": False, "message": "Connectez-vous pour consulter vos demandes."}), 401
    if authenticated_id != artisan_id:
        return jsonify({"success": False, "message": "Accès interdit."}), 403

    conn = get_db_connection()
    cursor = conn.cursor()
    demandes = cursor.execute('''
        SELECT d.*, s.titre_service 
        FROM demandes d
        JOIN services s ON d.service_id = s.id
        WHERE s.artisan_id = ?
        ORDER BY d.date_creation DESC
    ''', (artisan_id,)).fetchall()
    conn.close()
    return jsonify({"success": True, "data": [dict(d) for d in demandes]})

@app.route('/api/artisan/<int:artisan_id>/services', methods=['GET'])
def mes_services_artisan(artisan_id):
    authenticated_id = get_authenticated_artisan_id()
    if authenticated_id is None:
        return jsonify({"success": False, "message": "Connectez-vous pour consulter vos services."}), 401
    if authenticated_id != artisan_id:
        return jsonify({"success": False, "message": "Accès interdit."}), 403

    conn = get_db_connection()
    cursor = conn.cursor()
    services = cursor.execute('''
        SELECT * FROM services 
        WHERE artisan_id = ? AND (actif IS NULL OR actif = 1)
        ORDER BY date_creation DESC
    ''', (artisan_id,)).fetchall()
    conn.close()
    return jsonify({"success": True, "data": [dict(s) for s in services]})

@app.route('/api/demandes/<int:demande_id>/statut', methods=['PATCH'])
def changer_statut_demande(demande_id):
    artisan_id = get_authenticated_artisan_id()
    if artisan_id is None:
        return jsonify({"success": False, "message": "Connectez-vous pour modifier une demande."}), 401

    data = request.json or {}
    nouveau_statut = data.get('statut')
    if nouveau_statut not in {'Nouveau', 'Contacté', 'Terminé'}:
        return jsonify({"success": False, "message": "Statut invalide."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    demande = cursor.execute('''
        SELECT s.artisan_id
        FROM demandes d
        JOIN services s ON s.id = d.service_id
        WHERE d.id = ?
    ''', (demande_id,)).fetchone()
    if not demande:
        conn.close()
        return jsonify({"success": False, "message": "Demande introuvable."}), 404
    if demande['artisan_id'] != artisan_id:
        conn.close()
        return jsonify({"success": False, "message": "Accès interdit."}), 403

    cursor.execute('UPDATE demandes SET statut = ? WHERE id = ?', (nouveau_statut, demande_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Statut mis à jour."})

@app.route('/')
def home():
    with open('index.html', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/service-worker.js')
def service_worker():
    response = app.send_static_file('service-worker.js')
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-cache'
    return response

if __name__ == '__main__':
    print("Application SamaService Dakar lancée sur http://127.0.0.1:5000")
    app.run(debug=True, port=5000)