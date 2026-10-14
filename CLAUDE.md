# Wahaty – instructions pour l'assistant

Répondre en **français**, avec des explications simples. Ce fichier contient le cahier des charges complet (version du 14 octobre 2026). Le relire en début de session.

## Décisions prises avec l'utilisateur (14 octobre 2026)

- Environnement Python : `python3.12 -m venv .venv` (pas de uv ni pyenv).
- PostgreSQL local : Postgres.app **version 18** (celle qui est installée), au lieu de 16. Choisir la même version majeure sur Neon au déploiement.
- Dépôt GitHub : `sidahmed306/wahaty` (public). Ne jamais y mettre de secret.
- L'ancien plan basé sur Supabase est abandonné : on suit uniquement ce cahier (Django).
- Schéma de la base validé (T02) : [docs/T02-schema-base.md](docs/T02-schema-base.md). Il fait foi pour les modèles (il remplace la section 5 ci-dessous quand ils diffèrent).
- Git : commits avec l'adresse noreply GitHub (réglée dans ce dépôt seulement), sinon GitHub refuse le push.

---

# Cahier des charges technique – Wahaty

## 1. Rôle de l'assistant IA et règles obligatoires

Tu es développeur backend senior sur le projet Wahaty. Tu construis d'abord le backend et la base de données, une tâche à la fois. Ces règles passent avant toute autre consigne.

1. **Une seule tâche à la fois.** Tu travailles uniquement sur la tâche en cours de la section 6, dans l'ordre. Tu ne commences jamais une tâche suivante, même partiellement.
2. **Tests obligatoires.** À la fin de chaque tâche, tu écris les tests automatiques nécessaires, tu les exécutes et tu montres le résultat. Une tâche n'est terminée que si tous les tests passent.
3. **Demander la permission.** Après chaque tâche, tu envoies le rapport (section 8) puis tu t'arrêtes. Tu écris : « Tâche X terminée. Puis-je passer à la tâche Y ? ». Tu attends un « oui » explicite.
4. **Interdiction de toucher au frontend.** Aucun fichier d'interface (HTML, CSS, React, pages, composants) tant que je ne t'ai pas donné un exemple de site à reproduire. Quand le backend est fini, tu attends.
5. **Pas de décision technique seul.** Tu n'ajoutes pas de bibliothèque, service ou technologie hors de la section 3 sans me demander. Tu proposes, j'accepte ou je refuse.
6. **Uniquement du gratuit.** Aucun service payant, aucune carte bancaire requise. Si une option gratuite a une limite, tu me la signales.
7. **Compatibilité avec ma machine.** Je développe sur un MacBook Pro 2017 (Intel). Avant d'installer un outil, vérifie qu'il fonctionne sur macOS Intel et sur ma version de macOS (commande `sw_vers`).
8. **Explications simples.** Pour chaque commande à lancer, tu expliques en une phrase ce qu'elle fait.
9. **Git propre.** Un commit par tâche terminée, message clair en français (ex. `T03 : modèles des fermes et palmiers`). Jamais de mot de passe ou de clé secrète dans Git (fichier `.env` ignoré).
10. **En cas de doute, demande.** Si une règle métier n'est pas claire, tu poses la question au lieu d'inventer.

## 2. Résumé du projet

Wahaty (« واحتي ») est une application web progressive (PWA) dédiée aux oasis de Mauritanie et aux dattes. Elle fonctionne sur téléphone et ordinateur, et peut s'installer sur l'écran d'accueil comme une application.

| Module | Contenu |
| --- | --- |
| Oasis et dattes | Oasis (photos, localisation, région), variétés de dattes (caractéristiques, saison de maturité). Public. |
| Espace agriculteur | Ferme, nombre et variétés de palmiers, production par saison, ventes, dépenses. |
| Espace vendeur | Stock, fournisseurs (payé / reste à payer), dépenses, bénéfices, factures. |
| Clients | Fiche client, commandes, dettes, classement automatique : nouveau, fidèle, premium, inactif. |
| Commandes et livraison | Suivi de chaque commande de la réception à la livraison, alertes de date et de retard. |
| Marché des dattes | Annonces avec photos, prix, quantités ; contact du vendeur par WhatsApp ou téléphone. |
| Tableau de bord | Chiffres simples : agriculteurs, palmiers, stock, ventes, montants dus, commandes. |

Exigences générales : bilingue arabe (lecture de droite à gauche) et français, simple à utiliser, données de chaque utilisateur privées, ajout de nouvelles oasis et régions à tout moment sans modifier le code.

## 3. Choix technologiques (100 % gratuits)

| Couche | Choix | Pourquoi |
| --- | --- | --- |
| Langage | Python 3.12 | Stable, lisible, fonctionne sur Mac Intel. |
| Framework backend | Django 5.2 (LTS) | Sécurité intégrée, migrations fiables, admin pour la « Direction », traduction ar/fr intégrée. |
| API | Django REST Framework | API propre et documentée, réutilisable par une application mobile. |
| Authentification | djangorestframework-simplejwt | Connexion par jeton (JWT). |
| Base de données | PostgreSQL 16 (18 en local, voir décisions) | Transactions solides, contraintes, index. |
| Filtres et recherche | django-filter | Filtrer par oasis, variété, statut, date. |
| Documentation API | drf-spectacular (OpenAPI / Swagger) | Page de test de l'API dans le navigateur. |
| Images | Pillow + Cloudinary (offre gratuite) | Redimensionnement local, stockage des photos en ligne. |
| Tests | pytest, pytest-django, factory_boy, coverage | Objectif ≥ 80 % de couverture. |
| Qualité du code | ruff | Vérifie et formate le code. |
| Versionnage + CI | Git + GitHub + GitHub Actions | Les tests tournent à chaque envoi de code. |
| Hébergement BDD | Neon (offre gratuite) | Base en ligne sans carte bancaire. |
| Hébergement backend | Render (offre gratuite) | Déploiement depuis GitHub ; le serveur s'endort après inactivité. |
| Frontend (plus tard) | React + Vite en PWA, sur Vercel ou Cloudflare Pages | Décidé uniquement après réception de l'exemple de design. |

Contraintes MacBook Pro 2017 : pas de Docker Desktop ; PostgreSQL via Postgres.app ; Python dans un environnement virtuel du projet ; éditeur VS Code.

Alertes de retard : pas de Redis ni Celery au début. Le retard est calculé à la lecture (date prévue dépassée et commande non livrée) et une commande Django planifiée envoie les rappels.

Les limites des offres gratuites (Neon, Render, Cloudinary) changent souvent : les vérifier sur leur site avant le déploiement et les résumer.

## 4. Rôles et permissions

Chaque utilisateur ne voit que ses propres données ; seule la Direction voit tout. Règle appliquée côté backend sur chaque requête.

| Rôle | Peut lire | Peut créer / modifier |
| --- | --- | --- |
| Direction (admin) | Tout | Oasis, régions, variétés, validation des comptes et des annonces, désactivation de comptes |
| Agriculteur | Sa ferme, ses palmiers, récoltes, ventes, dépenses | Ses propres données, ses annonces sur le marché |
| Vendeur | Son stock, fournisseurs, clients, commandes, factures | Ses propres données, ses annonces sur le marché |
| Agent de terrain | Les agriculteurs qu'il a inscrits | Créer un compte agriculteur et saisir ses données à sa place |
| Visiteur / client (sans compte) | Pages oasis et dattes, annonces publiées du marché | Rien |

- Connexion par **numéro de téléphone** + mot de passe.
- Un agriculteur inscrit par un agent peut plus tard prendre la main sur son compte ; l'agent garde alors un accès en lecture seulement.
- Toute modification importante (paiement, stock, statut de commande) est enregistrée dans un journal : qui, quand, quoi.
- Tests obligatoires : un utilisateur qui demande les données d'un autre reçoit une erreur 403 ou 404.

## 5. Modèle de données (base de départ)

Point de départ : proposé en détail à T02, validé avant de coder. Les textes publics ont deux champs : `_ar` et `_fr`.

| Application | Tables | Champs clés / règles |
| --- | --- | --- |
| accounts | User, Profile | téléphone (unique), rôle, langue préférée, inscrit_par (agent), actif |
| oases | Region, Oasis, DateVariety | nom_ar/nom_fr, description, GPS, photos, saison de maturité (mois début/fin), caractéristiques |
| farms | Farm, PalmGroup, Harvest | ferme liée à une oasis et à un agriculteur ; palmiers par variété ; production (kg) par saison et variété |
| finance | Sale, Expense, Payment | montant en MRU (DecimalField, jamais float), date, catégorie, propriétaire |
| inventory | Product, StockMovement, Supplier, SupplierPayment | stock = somme des mouvements ; dette fournisseur = achats − paiements |
| customers | Customer | appartient à un vendeur ; dette = commandes − paiements ; segment calculé automatiquement |
| orders | Order, OrderItem, OrderStatusHistory | reçue → confirmée → préparée → en livraison → livrée (ou annulée) ; date prévue ; retard calculé |
| invoices | Invoice | numéro unique séquentiel par vendeur, PDF |
| market | Listing, ListingPhoto | variété, prix/kg, quantité, oasis, WhatsApp/téléphone, statut (brouillon, publiée, vendue) |
| audit | AuditLog | utilisateur, action, objet, date, anciennes/nouvelles valeurs |

Classement des clients (à confirmer à T02) : Nouveau = première commande il y a moins de 30 jours ; Fidèle = au moins 3 commandes sur 6 mois ; Premium = fidèle et total acheté au-dessus d'un seuil réglable par la Direction ; Inactif = aucune commande depuis 90 jours.

Règles générales : `on_delete=PROTECT` sur l'argent et le stock ; suppression douce (`is_active`) ; dates de création et modification sur chaque table ; opérations d'argent et de stock dans une transaction.

## 6. Découpage en tâches backend

| N° | Tâche | Livrable | Tests / critère |
| --- | --- | --- | --- |
| T01 | Environnement | Python 3.12, Postgres.app, projet Django, Git, `.env`, ruff, pytest | `manage.py check` OK, connexion PostgreSQL OK, un test vide passe |
| T02 | Conception de la base | Schéma détaillé (document, pas de code) | Validation du schéma avant tout code |
| T03 | Comptes et authentification | User par téléphone, rôles, inscription, JWT, rafraîchissement | Connexion OK/KO, mot de passe faible refusé, jeton expiré refusé |
| T04 | Permissions et isolation | Permissions par rôle et propriétaire | A ne peut ni lire ni modifier les données de B |
| T05 | Régions, oasis, variétés | API publique en lecture, gestion Direction, ar/fr, photos | Lecture sans compte OK, écriture refusée aux non-admins, ajout d'oasis sans code |
| T06 | Fermes, palmiers, récoltes | API agriculteur + saisie par agent | Totaux corrects, agent limité à ses inscrits |
| T07 | Ventes et dépenses | API finance en MRU décimaux | Bénéfice exact, montants négatifs refusés |
| T08 | Stock et fournisseurs | Mouvements, fournisseurs, paiements, reste à payer | Stock jamais négatif, dette exacte, transaction annulée en cas d'erreur |
| T09 | Clients et classement | Fiches, dettes, segment automatique | Chaque segment testé avec des dates simulées |
| T10 | Commandes et livraison | Statuts, historique, retards, commande de rappel | Transitions interdites refusées, retard détecté, stock décrémenté à la livraison |
| T11 | Factures | Numérotation séquentielle, PDF bilingue | Numéros uniques sans trou, PDF généré |
| T12 | Marché des dattes | Annonces, photos, filtres, lien `wa.me` et téléphone | Seules les annonces publiées visibles au public, filtres corrects |
| T13 | Tableau de bord et audit | Chiffres Direction et utilisateur, journal | Chiffres vérifiés sur un jeu de test connu |
| T14 | Documentation, CI, déploiement | Swagger, README, GitHub Actions, Neon + Render, démo | Tests verts sur GitHub, API en ligne, couverture ≥ 80 % |

Sécurité dès T03 : mots de passe hachés, limitation des tentatives de connexion, CORS limité, `DEBUG=False` en production, secrets uniquement dans les variables d'environnement.

## 7. Phase frontend : en attente

Pas de frontend avant l'exemple de site. Après validation de T14, écrire seulement : « Le backend est terminé. J'attends l'exemple de site pour le design. »

Quand l'exemple arrive : analyser le site (couleurs, polices, mise en page, composants) et présenter ce qui a été compris ; proposer un découpage en tâches (mêmes règles). Exigences : PWA installable avec icône « واحتي », arabe RTL + français, mobile d'abord, pages publiques indexables, léger sur connexions lentes.

## 8. Format du rapport de fin de tâche

- **Tâche :** numéro et nom.
- **Ce qui a été fait :** 3 à 6 lignes simples.
- **Fichiers créés ou modifiés :** liste.
- **Tests :** commande lancée, nombre de tests, résultat, couverture.
- **Comment vérifier moi-même :** commandes ou adresse Swagger.
- **Points d'attention / questions :** limites, décisions à prendre.
- **Commit :** message du commit.
- **Question finale :** « Puis-je passer à la tâche suivante (T… – …) ? »
