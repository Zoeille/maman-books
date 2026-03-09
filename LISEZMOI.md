# 📚 maman-books — Guide d'installation

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-zoeillle-ffdd00?style=flat&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/zoeillle)

> **Avertissement :** Ce projet est à but éducatif uniquement. Il s'agit d'une démonstration technique de développement de bots Telegram en Python. L'auteur décline toute responsabilité quant à l'usage que chacun en fait. Il appartient à chaque utilisateur de s'assurer que son utilisation est conforme aux lois en vigueur dans son pays ainsi qu'aux conditions d'utilisation des services tiers auxquels il se connecte.

---

> Ce guide est fait pour tout le monde, même sans aucune connaissance en informatique. Suis les étapes dans l'ordre et ça marchera !

---

## Ce dont tu as besoin

- Un ordinateur sous Windows, Mac ou Linux
- L'application Telegram (sur ton téléphone **et/ou** ton ordinateur)
- Une connexion internet

---

## Étape 1 — Télécharger le projet

1. Va sur la page des releases : **[github.com/Zoeille/maman-books/releases](https://github.com/Zoeille/maman-books/releases)**
2. Clique sur **Source code (zip)** sous la dernière version
3. Une fois téléchargé, **fais un clic droit** sur le fichier ZIP → **Extraire tout** (ou "Décompresser")
4. Choisis un endroit facile à retrouver (par exemple ton Bureau)

Tu devrais maintenant avoir un dossier `maman-books` quelque part sur ton ordinateur.

---

## Étape 2 — Installer Python

Python est le programme qui fait tourner le bot. C'est gratuit.

1. Va sur **[python.org/downloads](https://www.python.org/downloads/)**
2. Clique sur le gros bouton jaune **Download Python**
3. Ouvre le fichier téléchargé
4. ⚠️ **Très important** : avant de cliquer sur "Install Now", coche la case **"Add Python to PATH"** en bas de la fenêtre
5. Clique sur **Install Now** et attends que ça se termine
6. Clique sur **Close**

---

## Étape 3 — Créer ton bot Telegram

Tu vas créer ton propre bot via BotFather, le bot officiel de Telegram pour ça.

1. Ouvre Telegram
2. Dans la barre de recherche, tape **@BotFather** et ouvre la conversation
3. Envoie le message : `/newbot`
4. BotFather te demande un **nom** pour ton bot — c'est le nom qui s'affiche dans les conversations (exemple : `Ma Bibliothèque`)
5. Ensuite il te demande un **nom d'utilisateur** — ça doit être unique et terminer par `bot` (exemple : `ma_bibliotheque_bot`)
6. Si le nom est déjà pris, essaie-en un autre

BotFather va t'envoyer un message de confirmation avec une longue suite de caractères qui ressemble à ça :

```
1234567890:AAFabcdefghijklmnopqrstuvwxyz123456
```

**Copie ce token et garde-le précieusement** — tu en auras besoin juste après.

---

## Étape 4 — Trouver ton identifiant Telegram

Le bot n'accepte que les personnes que tu autorises. Pour ça, il a besoin de ton identifiant Telegram (un simple numéro).

1. Dans Telegram, cherche **@userinfobot** et ouvre la conversation
2. Envoie n'importe quel message (par exemple `/start`)
3. Il te répond avec tes infos. Repère la ligne **Id :** suivie d'un nombre (exemple : `Id: 123456789`)

**Note ce nombre** — c'est ton identifiant.

> Si tu veux que d'autres personnes puissent utiliser le bot, demande-leur de faire la même chose et de te donner leur identifiant Telegram.

---

## Étape 5 — Configurer le bot

C'est ici que tu vas entrer toutes tes informations.

1. Ouvre le dossier `maman-books`
2. Tu vois un fichier qui s'appelle **`.env.example`**

> ⚠️ Sur Windows, les fichiers commençant par un point sont parfois cachés. Si tu ne le vois pas : dans l'Explorateur de fichiers, clique sur **Affichage** → coche **Éléments masqués**.

3. **Fais une copie** de ce fichier (clic droit → Copier, puis clic droit → Coller)
4. **Renomme la copie** en **`.env`** (supprime le `.example` à la fin)

> Windows peut te dire que le fichier n'aura plus d'extension — c'est normal, confirme.

5. Fais un **clic droit sur `.env`** → **Ouvrir avec** → **Bloc-notes** (ou n'importe quel éditeur de texte)

Tu vois quelque chose comme ça :

```
TELEGRAM_TOKEN=
ALLOWED_USER_IDS=
ANNA_ARCHIVE_URL=
...
```

Remplis les lignes comme ceci :

```
TELEGRAM_TOKEN=colle-ici-le-token-de-botfather
ALLOWED_USER_IDS=ton-identifiant-telegram
ANNA_ARCHIVE_URL=colle-ici-l-url-de-ton-instance-anna
```

**Exemples concrets :**

```
TELEGRAM_TOKEN=1234567890:AAFabcdefghijklmnopqrstuvwxyz123456
ALLOWED_USER_IDS=123456789
ANNA_ARCHIVE_URL=https://example.com
```

> Pour ajouter plusieurs personnes autorisées, sépare leurs identifiants par des virgules :
> `ALLOWED_USER_IDS=123456789,987654321,555555555`

**Paramètres optionnels :**

| Ligne | À quoi ça sert |
|---|---|
| `ALLOWED_FORMATS=epub,pdf,mobi,azw3` | Les formats que le bot peut t'envoyer (voir détail ci-dessous). |
| `VIRUSTOTAL_API_KEY=` | Clé API [VirusTotal](https://www.virustotal.com) pour scanner les fichiers avant de les recevoir. Laisse vide pour désactiver. |
| `SMTP_HOST=smtp.gmail.com` | Adresse du serveur mail (pour envoyer les livres par email ou vers un Kindle). |
| `SMTP_PORT=587` | Port du serveur mail (laisse 587 par défaut). |
| `SMTP_USER=` | Ton adresse email (ex : `toi@gmail.com`). |
| `SMTP_PASSWORD=` | Mot de passe de ton email. Pour Gmail, utilise un **mot de passe d'application** (voir section Kindle ci-dessous). |
| `SMTP_FROM=` | Adresse d'expéditeur. Laisse vide pour utiliser `SMTP_USER`. |

**Quel format choisir ?**

Le bot peut te donner les livres dans différents formats :

- **EPUB** — idéal pour les liseuses (Kobo, etc.) et applications de lecture. Les Kindle **depuis 2022** lisent aussi l'EPUB nativement.
- **PDF** — s'ouvre partout, mise en page fixe
- **MOBI / AZW3** — formats Kindle, **nécessaires pour les vieux Kindle (avant 2022)**

Options possibles :
- `ALLOWED_FORMATS=epub,pdf,mobi,azw3` — le bot te **demande à chaque fois** quel format tu veux
- `ALLOWED_FORMATS=epub` — tu reçois **toujours de l'EPUB**, sans question
- `ALLOWED_FORMATS=epub,pdf` — choix entre EPUB et PDF uniquement

> La conversion en MOBI/AZW3 nécessite Calibre (voir l'étape optionnelle ci-dessous).

6. **Enregistre le fichier** (Ctrl+S) et ferme le Bloc-notes

---

## Étape 5b — (Optionnel) Installer Calibre pour les formats Kindle

Si tu veux envoyer des livres en **MOBI ou AZW3** (formats Kindle), installe Calibre :

1. Va sur **[calibre-ebook.com/download](https://calibre-ebook.com/download)**
2. Clique sur **Windows** (ou Mac/Linux selon ton système)
3. Lance l'installateur et suis les étapes (tout par défaut, c'est très simple)
4. Redémarre le bot ensuite

Le bot détecte Calibre automatiquement — tu verras `✓ ebook-convert trouvé` au démarrage.

> Sans Calibre, le bot essaie quand même de convertir mais le résultat peut varier. Pour envoyer vers Kindle par email, Amazon convertit lui-même les fichiers, donc Calibre n'est pas indispensable dans ce cas.

---

## Étape 5c — (Optionnel) Configurer l'envoi par email ou vers un Kindle

Le bot peut envoyer les livres directement par email ou sur ton Kindle, sans passer par Telegram.

### Configurer Gmail

1. Va sur **[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)**
2. Connecte-toi à ton compte Google
3. Dans "Nom de l'application", écris `maman-books` et clique **Créer**
4. Google te donne un mot de passe à 16 lettres (ex : `abcd efgh ijkl mnop`) — **copie-le**

Dans ton `.env`, remplis ces lignes :
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=toi@gmail.com
SMTP_PASSWORD=abcdefghijklmnop
SMTP_FROM=toi@gmail.com
```
(le mot de passe sans espaces)

### Configurer Send to Kindle

1. Va sur **[amazon.fr](https://www.amazon.fr)** → ton compte → **Gérer votre contenu et vos appareils**
2. Clique sur **Préférences** → **Paramètres des documents personnels**
3. Trouve **Liste des adresses e-mail autorisées pour les documents personnels** et ajoute `toi@gmail.com` (l'adresse que tu as mise dans `SMTP_FROM`)
4. Note ton adresse Kindle (du type `prenom@kindle.com`) — tu la rentreras dans le bot via `/settings`

### Dans le bot

Une fois le bot configuré et lancé, envoie `/settings` dans Telegram pour entrer ton adresse email et/ou ton adresse Kindle. Le bot te les demandera guidé étape par étape.

---

## Étape 6 — Installer et lancer le bot

1. Dans le dossier `maman-books`, double-clique sur le fichier **`lancer.bat`**
2. Une fenêtre noire s'ouvre — c'est normal, ne la ferme pas !
3. La première fois, ça installe les dépendances automatiquement (ça peut prendre une minute)
4. La fenêtre affiche d'abord la configuration active (sources activées, VirusTotal, formats…), puis `Bot started.` quand le bot est prêt

Ouvre Telegram, trouve ton bot par son nom d'utilisateur, envoie `/start` et c'est parti ! 🎉

> **Pour arrêter le bot :** ferme simplement la fenêtre noire.
> **Pour le relancer :** double-clique à nouveau sur `lancer.bat`.

---

## Utilisation

1. Envoie `/start` — au premier lancement, le bot te guide pour configurer tes préférences (format, email, adresse Kindle)
2. Envoie un titre de livre
3. Le bot cherche et t'affiche une liste de résultats — appuie sur un résultat
4. Si tu as configuré plusieurs formats, le bot te demande lequel tu veux
5. Si tu as configuré un email ou une adresse Kindle, le bot te demande où envoyer le livre (Telegram / Email / Kindle)
6. Le fichier t'est envoyé 📖

> Si tu as activé VirusTotal, le fichier est analysé automatiquement avant d'être envoyé. S'il est détecté comme dangereux, le bot le bloque et t'en informe.

Tu peux modifier tes préférences à tout moment avec la commande `/settings`.

---

## Pour les utilisateurs avancés — Docker

Si tu utilises Docker, une image toute prête est disponible :

```
ghcr.io/zoeille/maman-books:latest
```

Le fichier `docker-compose.yml` est déjà configuré pour l'utiliser.

---

## En cas de problème

- **"Python n'est pas reconnu"** → tu as oublié de cocher "Add Python to PATH" pendant l'installation. Désinstalle Python et recommence l'étape 2.
- **Le bot ne répond pas** → vérifie que la fenêtre noire est bien ouverte et que tu n'as pas de faute de frappe dans le `.env`.
- **"Aucun résultat trouvé"** → essaie avec un titre en anglais ou vérifie que `ANNA_ARCHIVE_URL` est bien rempli.
- **"Toutes les sources sont indisponibles"** → les DNS de ton opérateur internet bloquent parfois les serveurs de téléchargement (Libgen, etc.). Pour contourner ça, change les DNS de ta connexion pour utiliser ceux de Cloudflare (`1.1.1.1`) ou Google (`8.8.8.8`). Tuto complet : [Changer les DNS sur Windows — Le Crabe Info](https://lecrabeinfo.net/tutoriels/changer-les-dns-sur-windows/)
- **L'email n'arrive pas** → vérifie que `SMTP_USER` et `SMTP_PASSWORD` sont bien remplis dans `.env`. Pour Gmail, le mot de passe doit être un **mot de passe d'application** (pas ton mot de passe habituel).
- **Le livre n'arrive pas sur mon Kindle** → vérifie que l'adresse email de l'expéditeur (`SMTP_FROM`) est bien dans la liste des adresses autorisées sur ton compte Amazon.
- **Je reçois un EPUB au lieu de MOBI/AZW3** → installe Calibre (étape 5b). Sans Calibre, la conversion peut ne pas fonctionner correctement.
