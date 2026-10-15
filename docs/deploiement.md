# Mise en ligne de TRC (gratuite, sans carte bancaire)

Ordre : **Neon** (base) → **Cloudinary** (photos) → **Render** (API) → **Cloudflare Pages** (site)
→ **GitHub** (rappels quotidiens). Aucun secret ne va dans Git : on le colle dans chaque service.

## Limites des offres gratuites (vérifiées le 15 octobre 2026)

| Service | Limites | Conséquence pour TRC |
| --- | --- | --- |
| Neon | 1 Go par projet, 100 heures de calcul par mois, mise en veille après 5 min | Largement assez au début ; la 1re requête après une pause est un peu plus lente. |
| Render | 750 h par mois, mise en veille après 15 min sans visite, disque effacé à chaque redémarrage | Le 1er visiteur après une pause attend environ 1 minute. Les photos ne peuvent pas rester sur Render, d'où Cloudinary. |
| Cloudinary | 25 crédits par mois (1 crédit = 1 Go stocké, 1 Go affiché ou 1 000 transformations) | Les photos sont réduites à 1 600 px avant l'envoi : plusieurs milliers de photos possibles. |
| Cloudflare Pages | 500 constructions par mois, 20 000 fichiers, 25 Mo par fichier | Très largement suffisant. |
| GitHub Actions | Gratuit pour un dépôt public | Les rappels planifiés s'arrêtent si le dépôt n'a aucune activité pendant 60 jours (un clic les relance). |

Sources : render.com/docs/free, neon.com/pricing, cloudinary.com/pricing,
developers.cloudflare.com/pages/platform/limits.

## 1. Neon (déjà fait)

Console Neon → projet `wahaty` → **Connect** → cocher **Pooled connection** → copier l'adresse.
Elle sert de `DATABASE_URL` (Render) et de `NEON_DATABASE_URL` (GitHub).

## 2. Cloudinary

Console → **Settings** → **API Keys** → copier **API environment variable** :
`cloudinary://CLE_API:SECRET_API@NOM_DU_COMPTE` (la clé API est un nombre de 15 chiffres).
Remplacer `<your_api_key>` et `<your_api_secret>` par les vraies valeurs, sans les `< >`.

## 3. Render (API)

1. render.com → **New** → **Blueprint** → choisir le dépôt `sidahmed306/wahaty`.
2. Render lit `render.yaml` et prépare le service `trc-api`.
3. Coller les 2 secrets demandés : `DATABASE_URL` (Neon) et `CLOUDINARY_URL`.
4. **Apply**. Après la construction, l'API répond sur `https://trc-api-l8g7.onrender.com/api/health/`.
5. Onglet **Shell** du service (ou en local avec `DATABASE_URL` de Neon) :
   - `python manage.py seed_demo` → variétés + oasis (les photos partent chez Cloudinary) ;
   - `python manage.py createsuperuser` → compte Direction.

Si l'adresse du service n'est pas `trc-api-l8g7.onrender.com`, mettre la vraie adresse dans
`CSRF_TRUSTED_ORIGINS` (onglet **Environment**).

## 4. Cloudflare Pages (site)

1. dash.cloudflare.com → **Workers & Pages** → **Create** → **Pages** → **Connect to Git** →
   dépôt `sidahmed306/wahaty`.
2. Réglages de construction :
   - Framework : **Vite** (ou aucun) ;
   - Dossier racine (*Root directory*) : `frontend` ;
   - Commande : `npm run build` ; dossier de sortie : `dist` ;
   - Variables : `VITE_API_URL=https://trc-api-l8g7.onrender.com` et `NODE_VERSION=22`.
3. Le site est publié sur `https://<nom>.pages.dev`. Mettre exactement cette adresse dans
   `CORS_ALLOWED_ORIGINS` sur Render (sinon le site ne peut pas appeler l'API).

## 5. GitHub (rappels quotidiens)

Dépôt → **Settings** → **Secrets and variables** → **Actions** → **New repository secret** :
nom `NEON_DATABASE_URL`, valeur = adresse Neon. Test immédiat : onglet **Actions** →
« Rappels quotidiens » → **Run workflow**.

## Plus tard : nom de domaine

1. Cloudflare Pages → **Custom domains** → ajouter le domaine (ex. `trc.mr`).
2. Render → `CORS_ALLOWED_ORIGINS=https://trc.mr,https://<nom>.pages.dev`.
Aucun changement de code.
