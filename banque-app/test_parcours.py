"""
Test du parcours complet de la banque (BPC).

Lancer depuis le dossier banque-app :
    python -m unittest -v test_parcours

Par défaut le test utilise une base SQLite temporaire (la vraie banque.db
n'est pas touchée). Pour le jouer contre PostgreSQL (sur la VM) :
    DATABASE_URL="postgresql://user:mdp@127.0.0.1/banque" python -m unittest -v test_parcours
"""
import os
import re
import tempfile
import unittest
import uuid
from decimal import Decimal

if not os.environ.get("DATABASE_URL"):
    _tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    _tmp.close()
    os.environ["SQLITE_PATH"] = _tmp.name

import app as banque  # noqa: E402

NUMERO = re.compile(r"Compte (BPC[0-9A-F]{8})")
SOLDE = re.compile(r'class="compte-solde">([0-9.\-]+) €')


class ParcoursComplet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        banque.app.config["TESTING"] = True
        with banque.app.app_context():
            banque.init_db()
        # Emails uniques : le test peut être rejoué sur une base existante.
        suffixe = uuid.uuid4().hex[:8]
        cls.email_a = f"alice-{suffixe}@test.local"
        cls.email_b = f"bob-{suffixe}@test.local"

    @classmethod
    def tearDownClass(cls):
        chemin = os.environ.get("SQLITE_PATH")
        if chemin and not os.environ.get("DATABASE_URL"):
            os.unlink(chemin)

    # --- Outils ---
    def client(self):
        return banque.app.test_client()

    def inscrire(self, c, nom, email, mdp="secret123"):
        r = c.post("/inscription", data={"nom": nom, "email": email, "mot_de_passe": mdp})
        self.assertEqual(r.status_code, 302, "l'inscription doit rediriger vers la connexion")
        self.assertIn("/connexion", r.headers["Location"])

    def connecter(self, c, email, mdp="secret123"):
        return c.post("/connexion", data={"email": email, "mot_de_passe": mdp})

    def compte(self, c):
        page = c.get("/mon-compte").get_data(as_text=True)
        return NUMERO.search(page).group(1), Decimal(SOLDE.search(page).group(1)), page

    def virer(self, c, source, dest, montant):
        return c.post("/virement", data={"source": source, "dest": dest, "montant": montant},
                      follow_redirects=True).get_data(as_text=True)

    # --- Le parcours ---
    def test_parcours_complet(self):
        a, b = self.client(), self.client()

        # 1. Création de deux comptes clients
        self.inscrire(a, "Alice Martin", self.email_a)
        self.inscrire(b, "Bob Durand", self.email_b)

        # Mot de passe stocké haché, jamais en clair
        with banque.app.app_context():
            row = banque.query("SELECT mot_de_passe FROM clients WHERE email = ?",
                               (self.email_a,), one=True)
        self.assertNotEqual(row["mot_de_passe"], "secret123")
        self.assertTrue(row["mot_de_passe"].startswith(("scrypt:", "pbkdf2:")))

        # 2. Connexion (mauvais mot de passe refusé, bon accepté)
        r = self.connecter(a, self.email_a, "mauvais")
        self.assertIn("incorrect", r.get_data(as_text=True))
        self.assertEqual(self.connecter(a, self.email_a).status_code, 302)
        self.assertEqual(self.connecter(b, self.email_b).status_code, 302)

        # 3. Consultation : numéro unique et solde initial de 100 €
        num_a, solde_a, _ = self.compte(a)
        num_b, solde_b, _ = self.compte(b)
        self.assertNotEqual(num_a, num_b)
        self.assertEqual((solde_a, solde_b), (Decimal("100.00"), Decimal("100.00")))

        # 4. Virements refusés
        cas_refuses = [
            (num_b, "150", "Solde insuffisant"),
            ("BPC00000000", "10", "existe pas"),  # l'apostrophe est échappée en HTML
            (num_b, "0", "positif"),
            (num_b, "-5", "positif"),
            (num_b, "NaN", "Montant invalide"),
            (num_b, "abc", "Montant invalide"),
            (num_b, "1.005", "centimes"),
            (num_a, "10", "vers le même compte"),
        ]
        for dest, montant, attendu in cas_refuses:
            with self.subTest(dest=dest, montant=montant):
                self.assertIn(attendu, self.virer(a, num_a, dest, montant))
        self.assertEqual(self.compte(a)[1], Decimal("100.00"))
        self.assertEqual(self.compte(b)[1], Decimal("100.00"))

        # On ne peut pas débiter le compte de quelqu'un d'autre
        self.assertIn("Compte source invalide", self.virer(a, num_b, num_a, "10"))

        # 5. Virement valide de 30 € de A vers B
        self.assertIn("Virement de 30.00 € effectué", self.virer(a, num_a, num_b, "30"))
        num, solde_a, page_a = self.compte(a)
        num, solde_b, page_b = self.compte(b)
        self.assertEqual(solde_a, Decimal("70.00"))
        self.assertEqual(solde_b, Decimal("130.00"))
        # L'opération apparaît dans l'historique des deux clients
        self.assertIn("-30.00 €", page_a)
        self.assertIn("+30.00 €", page_b)

        # 6. Messagerie client -> conseiller -> client
        a.post("/messages", data={"contenu": "Bonjour, question sur mon virement"})
        conseiller = self.client()
        r = self.connecter(conseiller, "conseiller@banque.local", "conseiller")
        self.assertIn("/conseiller", r.headers["Location"])

        liste = conseiller.get("/conseiller").get_data(as_text=True)
        self.assertIn("Alice Martin", liste)
        self.assertNotIn("Bob Durand", liste)  # Bob n'a pas écrit
        client_id = int(re.search(r'/conseiller/(\d+)">Alice Martin', liste).group(1))

        fil = conseiller.get(f"/conseiller/{client_id}").get_data(as_text=True)
        self.assertIn("Bonjour, question sur mon virement", fil)
        conseiller.post(f"/conseiller/{client_id}", data={"contenu": "Votre virement est bien passé."})

        conversation = a.get("/messages").get_data(as_text=True)
        self.assertLess(conversation.index("question sur mon virement"),
                        conversation.index("Votre virement est bien passé."))
        self.assertIn('bulle autre', conversation)  # réponse du conseiller, côté gauche

        # Un client ne peut pas accéder à l'espace conseiller
        self.assertEqual(a.get("/conseiller").status_code, 302)

        # 7. Déconnexion
        a.get("/deconnexion")
        r = a.get("/mon-compte")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/connexion", r.headers["Location"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
