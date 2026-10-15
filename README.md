# TRC – إرث النخيل

Plateforme des dattes et des oasis de l'Adrar (Mauritanie) : variétés et oasis en accès public,
marché des dattes avec contact WhatsApp, espaces privés pour les agriculteurs, les vendeurs, les
agents de terrain et la Direction. Bilingue **arabe** (par défaut, de droite à gauche) et
**français**, pensée d'abord pour le téléphone, installable comme une application (PWA).

| Partie | Technologie | Hébergement (gratuit) |
| --- | --- | --- |
| API | Python 3.12, Django 5.2, Django REST Framework, JWT | Render |
| Base de données | PostgreSQL 18 | Neon |
| Photos | Pillow (redimensionnement) + Cloudinary | Cloudinary |
| Site | React 19 + Vite, PWA, i18next | Cloudflare Pages |
| Tests | pytest (backend), Vitest (site) | GitHub Actions |

## Ce que fait la plateforme

- **Public** : 9 variétés de dattes (سلمدينة، الحمر، سكاني…), oasis par région (Atar, Chinguetti,
  Ouadane, Aoujeft), marché des annonces validées, bouton WhatsApp / appel.
- **Agriculteur** : fermes, palmiers par variété (productifs / jeunes), récoltes par saison,
  ventes directes, dépenses, bilan.
- **Vendeur** : produits et stock (jamais négatif), fournisseurs et reste à payer, achats, clients
  (dette, classement automatique nouveau / fidèle / premium / inactif), commandes (reçue →
  confirmée → préparée → en livraison → livrée), factures PDF bilingues numérotées sans trou.
- **Agent de terrain** : inscrit des agriculteurs et saisit pour eux ; code de reprise du compte.
- **Direction** : validation des comptes et des annonces, tableau de bord, journal d'audit
  (non modifiable), réglages, oasis et variétés dans l'administration.

## Installer sur un Mac (développement)

Prérequis : Python 3.12, [Postgres.app](https://postgresapp.com), Node.js 22 (via nvm).

```bash
# Backend
python3.12 -m venv .venv                 # crée l'environnement Python du projet
source .venv/bin/activate                # l'active
pip install -r requirements.txt          # installe les bibliothèques
cp .env.example .env                     # puis remplir .env (jamais envoyé sur GitHub)
python manage.py migrate                 # crée les tables
python manage.py seed_demo               # variétés + oasis de démonstration
python manage.py createsuperuser         # compte Direction
python manage.py runserver               # API sur http://127.0.0.1:8000

# Site (dans un 2e terminal)
cd frontend
nvm use 22                               # Node.js 22
npm install                              # installe les bibliothèques du site
npm run dev                              # site sur http://localhost:5173
```

## Tests

```bash
pytest --cov                    # backend : tests + couverture (doit rester ≥ 80 %)
cd frontend && npm test         # site
cd frontend && npm run coverage # site avec couverture
```

Les tests du backend utilisent la base locale (`TEST_DATABASE_URL`), jamais Neon. Ils tournent
aussi sur GitHub à chaque envoi de code (onglet **Actions**).

## Documentation de l'API

- Swagger : `/api/docs/` (bouton **Authorize** avec le jeton reçu de `POST /api/auth/login/`).
- Schéma OpenAPI : `/api/schema/`.
- Langue des messages : en-tête `Accept-Language: ar` (défaut) ou `fr`.

## Commandes utiles

| Commande | Rôle |
| --- | --- |
| `python manage.py seed_varieties` | crée ou met à jour les 9 variétés du flyer et leurs photos |
| `python manage.py seed_demo` | variétés + une oasis par région de l'Adrar |
| `python manage.py send_order_reminders` | notifications du jour (lancée chaque matin par GitHub Actions) |
| `python manage.py makemessages -l ar` puis `compilemessages` | mettre à jour les traductions arabes (`locale/ar/`) |

## Mise en ligne

Le détail pas à pas est dans [docs/deploiement.md](docs/deploiement.md).

1. **Neon** : base PostgreSQL (adresse « pooled »).
2. **Render** : *New > Blueprint* avec ce dépôt (fichier `render.yaml`), puis coller
   `DATABASE_URL` et `CLOUDINARY_URL` dans Render.
3. **Cloudflare Pages** : dossier `frontend`, commande `npm run build`, sortie `dist`,
   variable `VITE_API_URL=https://trc-api.onrender.com`.
4. **GitHub** : secret `NEON_DATABASE_URL` pour les rappels quotidiens.

## Sécurité

- Aucun secret dans Git : tout est dans `.env` (local) ou dans Render / GitHub (production).
- Mots de passe hachés, tentatives de connexion limitées, comptes validés par la Direction.
- Chaque utilisateur ne voit que ses données (testé : 403 / 404 sinon).
- Production : `DEBUG=False`, HTTPS obligatoire, seul le site TRC peut appeler l'API (CORS).
