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

1. En haut de cette page GitHub, clique sur le bouton vert **`<> Code`**
2. Clique sur **Download ZIP**
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

> Si tu veux que d'autres personnes puissent utiliser le bot, demande-leur de faire la même chose et de te donner leur numéro.

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

6. **Enregistre le fichier** (Ctrl+S) et ferme le Bloc-notes

---

## Étape 6 — Installer et lancer le bot

1. Dans le dossier `maman-books`, double-clique sur le fichier **`lancer.bat`**
2. Une fenêtre noire s'ouvre — c'est normal, ne la ferme pas !
3. La première fois, ça installe les dépendances automatiquement (ça peut prendre une minute)
4. Quand tu vois `Bot started.` dans la fenêtre, le bot est prêt

Ouvre Telegram, trouve ton bot par son nom d'utilisateur, envoie `/start` et c'est parti ! 🎉

> **Pour arrêter le bot :** ferme simplement la fenêtre noire.
> **Pour le relancer :** double-clique à nouveau sur `lancer.bat`.

---

## Utilisation

1. Envoie un titre de livre au bot
2. Il cherche et t'affiche une liste de résultats
3. Appuie sur un résultat
4. Le fichier t'est envoyé directement dans Telegram 📖

---

## En cas de problème

- **"Python n'est pas reconnu"** → tu as oublié de cocher "Add Python to PATH" pendant l'installation. Désinstalle Python et recommence l'étape 2.
- **Le bot ne répond pas** → vérifie que la fenêtre noire est bien ouverte et que tu n'as pas de faute de frappe dans le `.env`.
- **"Aucun résultat trouvé"** → essaie avec un titre en anglais ou vérifie que `ANNA_ARCHIVE_URL` est bien rempli.
