import os
import tempfile
import unittest

_test_database = tempfile.TemporaryDirectory()
os.environ.pop('DATABASE_URL', None)
os.environ.pop('REQUIRE_POSTGRES', None)
os.environ['DATABASE_PATH'] = os.path.join(_test_database.name, 'security-tests.db')
os.environ['CORS_ORIGINS'] = 'capacitor://localhost,http://localhost,https://localhost'

import app as application


class ApiSecurityTests(unittest.TestCase):
    def setUp(self):
        self.client = application.app.test_client()
        conn = application.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM demandes')
        cursor.execute('DELETE FROM services')
        cursor.execute('DELETE FROM artisans')
        conn.commit()
        conn.close()

    def register_artisan(self, name, telephone):
        response = self.client.post('/api/artisan/inscription', json={
            'nom': name,
            'telephone': telephone,
            'mot_de_passe': 'long-password-123',
            'metier': 'Plombier',
            'quartier': 'Dakar-Plateau'
        })
        self.assertEqual(response.status_code, 201)
        return response.get_json()['artisan']

    @staticmethod
    def auth_headers(artisan):
        return {'Authorization': f"Bearer {artisan['photo_token']}"}

    def create_service(self, artisan):
        response = self.client.post(
            '/api/services',
            headers=self.auth_headers(artisan),
            json={'titre_service': 'Service', 'description_service': 'Description'}
        )
        self.assertEqual(response.status_code, 201)
        return self.client.get(
            f"/api/artisan/{artisan['id']}/services",
            headers=self.auth_headers(artisan)
        ).get_json()['data'][0]['id']

    def test_artisan_routes_require_authentication(self):
        self.assertEqual(self.client.post('/api/services', json={}).status_code, 401)
        self.assertEqual(self.client.get('/api/artisan/1/services').status_code, 401)
        self.assertEqual(self.client.get('/api/artisan/1/demandes').status_code, 401)
        self.assertEqual(self.client.patch('/api/artisan/profil', json={}).status_code, 401)

    def test_profile_update_saves_valid_fields_and_rejects_invalid_values(self):
        artisan = self.register_artisan('Artisan', '770000001')
        headers = self.auth_headers(artisan)
        profile = {
            'nom': 'Nouveau nom',
            'telephone': '770000003',
            'metier': 'Électricien',
            'quartier': 'Yoff'
        }

        response = self.client.patch('/api/artisan/profil', headers=headers, json=profile)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['artisan']['nom'], 'Nouveau nom')
        self.assertEqual(response.get_json()['artisan']['telephone'], '770000003')
        self.assertNotIn('mot_de_passe', response.get_json()['artisan'])
        self.assertEqual(
            self.client.get(
                f"/api/artisan/{artisan['id']}/services",
                headers=headers
            ).status_code,
            200
        )
        self.assertEqual(
            self.client.patch(
                '/api/artisan/profil',
                headers=headers,
                json={**profile, 'metier': 'Métier inconnu'}
            ).status_code,
            400
        )

    def test_profile_update_rejects_duplicate_phone(self):
        artisan = self.register_artisan('Artisan', '770000001')
        self.register_artisan('Autre artisan', '770000002')

        response = self.client.patch(
            '/api/artisan/profil',
            headers=self.auth_headers(artisan),
            json={
                'nom': 'Artisan',
                'telephone': '770000002',
                'metier': 'Plombier',
                'quartier': 'Dakar-Plateau'
            }
        )
        self.assertEqual(response.status_code, 409)

    def test_account_deletion_requires_password_and_removes_only_related_data(self):
        artisan = self.register_artisan('Artisan', '770000001')
        other = self.register_artisan('Autre artisan', '770000002')
        artisan_service_id = self.create_service(artisan)
        other_service_id = self.create_service(other)
        for service_id in (artisan_service_id, other_service_id):
            self.client.post('/api/demandes', json={
                'service_id': service_id,
                'nom_client': 'Client',
                'telephone_client': '771234567',
                'description_besoin': 'Besoin'
            })

        self.assertEqual(
            self.client.delete(
                '/api/artisan/compte',
                json={'mot_de_passe': 'long-password-123'}
            ).status_code,
            401
        )
        self.assertEqual(
            self.client.delete(
                '/api/artisan/compte',
                headers=self.auth_headers(artisan),
                json={'mot_de_passe': 'incorrect'}
            ).status_code,
            401
        )

        response = self.client.delete(
            '/api/artisan/compte',
            headers=self.auth_headers(artisan),
            json={'mot_de_passe': 'long-password-123'}
        )
        self.assertEqual(response.status_code, 200)

        conn = application.get_db_connection()
        cursor = conn.cursor()
        self.assertEqual(
            cursor.execute('SELECT COUNT(*) AS count FROM artisans WHERE id = ?', (artisan['id'],)).fetchone()['count'],
            0
        )
        self.assertEqual(
            cursor.execute('SELECT COUNT(*) AS count FROM services WHERE artisan_id = ?', (artisan['id'],)).fetchone()['count'],
            0
        )
        self.assertEqual(
            cursor.execute('SELECT COUNT(*) AS count FROM demandes WHERE service_id = ?', (artisan_service_id,)).fetchone()['count'],
            0
        )
        self.assertEqual(
            cursor.execute('SELECT COUNT(*) AS count FROM demandes WHERE service_id = ?', (other_service_id,)).fetchone()['count'],
            1
        )
        conn.close()

    def test_artisans_can_only_manage_their_own_services_and_requests(self):
        owner = self.register_artisan('Owner', '770000001')
        other = self.register_artisan('Other', '770000002')
        service_id = self.create_service(owner)

        self.assertEqual(
            self.client.get(
                f"/api/artisan/{owner['id']}/services",
                headers=self.auth_headers(other)
            ).status_code,
            403
        )
        self.assertEqual(
            self.client.delete(
                f'/api/services/{service_id}',
                headers=self.auth_headers(other)
            ).status_code,
            404
        )

        self.client.post('/api/demandes', json={
            'service_id': service_id,
            'nom_client': 'Client',
            'telephone_client': '771234567',
            'description_besoin': 'Besoin'
        })
        request_id = self.client.get(
            f"/api/artisan/{owner['id']}/demandes",
            headers=self.auth_headers(owner)
        ).get_json()['data'][0]['id']

        self.assertEqual(
            self.client.patch(
                f'/api/demandes/{request_id}/statut',
                headers=self.auth_headers(other),
                json={'statut': 'Terminé'}
            ).status_code,
            403
        )
        self.assertEqual(
            self.client.patch(
                f'/api/demandes/{request_id}/statut',
                headers=self.auth_headers(owner),
                json={'statut': 'invalide'}
            ).status_code,
            400
        )

    def test_inactive_service_cannot_receive_a_request(self):
        artisan = self.register_artisan('Owner', '770000001')
        service_id = self.create_service(artisan)
        self.client.delete(
            f'/api/services/{service_id}',
            headers=self.auth_headers(artisan)
        )

        response = self.client.post('/api/demandes', json={
            'service_id': service_id,
            'nom_client': 'Client',
            'telephone_client': '771234567',
            'description_besoin': 'Besoin'
        })
        self.assertEqual(response.status_code, 404)

    def test_cors_rejects_unconfigured_origins(self):
        response = self.client.get(
            '/api/metadonnees',
            headers={'Origin': 'https://attacker.example'}
        )
        self.assertNotIn('Access-Control-Allow-Origin', response.headers)


if __name__ == '__main__':
    unittest.main()