# Déploiement en production — Poissonnerie

Guide complet pour un VPS **Ubuntu 24.04** neuf. Chaque bloc de commandes
s'exécute en SSH sur le serveur, en tant que root (ou avec `sudo`).

Prérequis : un VPS (2 Go de RAM suffisent largement), un sous-domaine
pointant vers l'IP du serveur (enregistrement DNS de type A, par exemple
`stock.mondomaine.com`), et ce dépôt de code.

---

## 1. Préparation du serveur

```bash
apt update && apt upgrade -y
apt install -y python3.12 python3.12-venv python3-pip nginx mysql-server \
               certbot python3-certbot-nginx git ufw

# Pare-feu : SSH + web uniquement
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable

# Utilisateur applicatif dédié (jamais root pour l'application)
adduser --system --group --home /opt/poissonnerie poissonnerie
mkdir -p /var/log/poissonnerie
chown poissonnerie:poissonnerie /var/log/poissonnerie
```

## 2. MySQL sécurisé

```bash
mysql_secure_installation
# Répondre : mot de passe root fort, supprimer les utilisateurs anonymes,
# désactiver la connexion root distante, supprimer la base test.

mysql -u root -p
```

```sql
CREATE DATABASE poissonnerie CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'poissonnerie_app'@'localhost' IDENTIFIED BY 'MOT-DE-PASSE-FORT-ICI';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES, DROP
      ON poissonnerie.* TO 'poissonnerie_app'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

Pour les sauvegardes automatiques, créer `/root/.my.cnf` (lisible par root
uniquement) :

```ini
[client]
user=root
password=MOT-DE-PASSE-ROOT-MYSQL
```

```bash
chmod 600 /root/.my.cnf
```

## 3. Installation de l'application

```bash
cd /opt/poissonnerie
# Copier le code ici (git clone, scp ou sftp), puis :
python3.12 -m venv venv
./venv/bin/pip install -r requirements.txt

# Configuration production
cp .env.example .env
nano .env
```

Contenu du `.env` de production :

```ini
FLASK_ENV=prod
SECRET_KEY=GENERER-UNE-LONGUE-CLE-ALEATOIRE     # python3 -c "import secrets; print(secrets.token_hex(32))"
MYSQL_HOST=localhost
MYSQL_USER=poissonnerie_app
MYSQL_PASSWORD=MOT-DE-PASSE-FORT-ICI
MYSQL_DB=poissonnerie
```

```bash
# Créer les tables et les données initiales
export FLASK_APP=run.py FLASK_ENV=prod
./venv/bin/flask db upgrade
./venv/bin/python seed.py            # 3 boutiques DONA + 5 comptes
./venv/bin/python seed_produits.py   # les 28 produits

chown -R poissonnerie:poissonnerie /opt/poissonnerie
```

> ⚠️ Ne JAMAIS exécuter `seed_demo.py` en production. Et changer le mot de
> passe du compte `admin` dès la première connexion (menu Utilisateurs).

## 4. Gunicorn en service systemd

```bash
cp deploy/poissonnerie.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now poissonnerie
systemctl status poissonnerie      # doit être "active (running)"
```

## 5. Nginx en reverse proxy

```bash
cp deploy/nginx-poissonnerie.conf /etc/nginx/sites-available/poissonnerie
nano /etc/nginx/sites-available/poissonnerie   # remplacer stock.mondomaine.com
ln -s /etc/nginx/sites-available/poissonnerie /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

À ce stade, `http://stock.mondomaine.com` doit afficher la page de connexion.

## 6. HTTPS avec Let's Encrypt

```bash
certbot --nginx -d stock.mondomaine.com
# Choisir la redirection automatique HTTP -> HTTPS.
# Le renouvellement est automatique (timer systemd certbot).
certbot renew --dry-run   # vérification
```

## 7. Sauvegardes automatiques (rotation 30 jours)

```bash
cp deploy/backup_mysql.sh /opt/poissonnerie/deploy/   # déjà présent si git
chmod +x /opt/poissonnerie/deploy/backup_mysql.sh
crontab -e
```

Ajouter la ligne :

```cron
0 2 * * * /opt/poissonnerie/deploy/backup_mysql.sh
```

Tester immédiatement : `bash /opt/poissonnerie/deploy/backup_mysql.sh`
puis vérifier `/var/backups/poissonnerie/`.

Restauration si besoin :

```bash
gunzip < /var/backups/poissonnerie/poissonnerie_2026-07-02.sql.gz | mysql poissonnerie
```

## 8. Mises à jour de l'application

```bash
cd /opt/poissonnerie
# Déployer le nouveau code (git pull / scp), puis :
./venv/bin/pip install -r requirements.txt
export FLASK_APP=run.py FLASK_ENV=prod
./venv/bin/flask db upgrade
systemctl restart poissonnerie
```

## 9. Vérifications post-déploiement

- [ ] Connexion HTTPS avec le cadenas vert
- [ ] Login admin, changement des 5 mots de passe par défaut
- [ ] Vérifier l'affectation des caissiers à leur boutique
- [ ] Création des comptes gérant et vendeurs (menu Utilisateurs)
- [ ] Ajustement des prix réels des 28 produits (menu Produits)
- [ ] Une vente test + impression du ticket 58 mm depuis le téléphone
- [ ] Une clôture test + réouverture admin
- [ ] Export Excel et PDF depuis le tableau de bord
- [ ] Présence de la première sauvegarde dans /var/backups/poissonnerie

## Dépannage rapide

| Symptôme | Piste |
|---|---|
| 502 Bad Gateway | `systemctl status poissonnerie` puis `/var/log/poissonnerie/error.log` |
| Erreur MySQL au démarrage | vérifier `.env` (utilisateur/mot de passe/base) |
| Migrations en erreur | `./venv/bin/flask db current` pour voir la révision appliquée |
| Ticket mal cadré | tester l'aperçu 58 mm depuis le navigateur du téléphone du vendeur |
