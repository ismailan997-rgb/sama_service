import os
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS

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

try:
    from werkzeug.security import generate_password_hash, check_password_hash
    HAS_WERKZEUG = True
except ImportError:
    HAS_WERKZEUG = False

app = Flask(__name__)
CORS(app)

# Liste des quartiers populaires de Dakar
QUARTIERS_DAKAR = [
    "Almadies", "Ngor", "Ouakam", "Yoff", "Mermoz", "Sacré-Cœur", 
    "Fann - Point E", "Médina", "Dakar-Plateau", "Grand Dakar",
    "Liberté 1-6", "Dieuppeul - Derklé", "Hann Maristes", "Grand Yoff",
    "Parcelles Assainies", "Pikine", "Guédiawaye", "Keur Massar", "Rufisque"
]

METIERS_LISTE = [
    {"id": "mecanicien", "nom": "Mécanicien Auto / Moto", "icone": "fa-wrench"},
    {"id": "plombier", "nom": "Plombier", "icone": "fa-faucet"},
    {"id": "electricien", "nom": "Électricien", "icone": "fa-bolt"},
    {"id": "climatisation", "nom": "Climatisation / Froid", "icone": "fa-snowflake"},
    {"id": "menuisier", "nom": "Menuisier Bois / Aluminium", "icone": "fa-hammer"},
    {"id": "peintre", "nom": "Peintre en Bâtiment", "icone": "fa-paint-roller"},
    {"id": "serrurier", "nom": "Serrurier", "icone": "fa-key"},
    {"id": "nettoyage", "nom": "Nettoyage & Débouchage", "icone": "fa-broom"}
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

    mdp_stocke = generate_password_hash(mot_de_passe) if HAS_WERKZEUG else mot_de_passe

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
                "note": 5.0
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
        SELECT id, nom, telephone, mot_de_passe, metier, quartier, note FROM artisans
        WHERE telephone = ?
    ''', (telephone,)).fetchone()
    
    if artisan:
        # Vérification avec hachage ou rétrocompatibilité mot de passe en clair
        mot_de_passe_db = artisan['mot_de_passe']
        valide = False
        if HAS_WERKZEUG:
            if mot_de_passe_db.startswith('scrypt:') or mot_de_passe_db.startswith('pbkdf2:'):
                valide = check_password_hash(mot_de_passe_db, mot_de_passe)
            else:
                valide = (mot_de_passe_db == mot_de_passe)
                if valide:
                    # Mise à jour avec le hash
                    nouveau_hash = generate_password_hash(mot_de_passe)
                    cursor.execute('UPDATE artisans SET mot_de_passe = ? WHERE id = ?', (nouveau_hash, artisan['id']))
                    conn.commit()
        else:
            valide = (mot_de_passe_db == mot_de_passe)

        if valide:
            res_artisan = {
                "id": artisan["id"],
                "nom": artisan["nom"],
                "telephone": artisan["telephone"],
                "metier": artisan["metier"],
                "quartier": artisan["quartier"],
                "note": artisan["note"] if "note" in artisan.keys() else 5.0
            }
            conn.close()
            return jsonify({"success": True, "artisan": res_artisan})

    conn.close()
    return jsonify({"success": False, "message": "Numéro de téléphone ou mot de passe incorrect."}), 401

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
    artisan_id = data.get('artisan_id')
    titre = data.get('titre_service', '').strip()
    description = data.get('description_service', '').strip()
    tarif = data.get('tarif_indicatif', '').strip() or 'Sur devis'

    if not artisan_id or not titre or not description:
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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE services SET actif = 0 WHERE id = ?', (service_id,))
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
    cursor.execute('''
        INSERT INTO demandes (service_id, nom_client, telephone_client, description_besoin, statut)
        VALUES (?, ?, ?, ?, 'Nouveau')
    ''', (service_id, nom_client, telephone_client, description))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Votre demande a été envoyée à l'artisan !"}), 201

@app.route('/api/artisan/<int:artisan_id>/demandes', methods=['GET'])
def mes_demandes(artisan_id):
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
    data = request.json or {}
    nouveau_statut = data.get('statut', 'Nouveau')
    conn = get_db_connection()
    cursor = conn.cursor()
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