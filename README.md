# discord-bots-infra

Infrastructure complète pour l'hébergement d'un parc de bots Discord sur Debian 12.
Le projet couvre le provisionnement, le durcissement système, le déploiement conteneurisé,
et la supervision, de bout en bout et sans intervention manuelle.

---

## Architecture

```
                    Internet / Discord API
                           |
              +------------+------------+
              |    Hetzner Cloud Firewall |
              |  (deny-all inbound sauf  |
              |   SSH:2222 depuis IPs    |
              |   autorisées)            |
              +------------+------------+
                           |
              +------------+------------+
              |      Debian 12 (VM)      |
              |                          |
              |  UFW (iptables backend)  |
              |  fail2ban (SSH)          |
              |                          |
              |  +--------------------+  |
              |  |   Docker Engine    |  |
              |  |                    |  |
              |  |  bot-moderation    |  |
              |  |  (Python 3.12)     |  |
              |  |                    |  |
              |  |  bot-status        |  |
              |  |  (Node.js 20)      |  |
              |  +--------------------+  |
              |                          |
              |  +--------------------+  |
              |  | Stack monitoring   |  |
              |  | Prometheus  :9090  |  |
              |  | Grafana     :3000  |  |
              |  | Node Exporter:9100 |  |
              |  | cAdvisor    :8080  |  |
              |  | (loopback only)    |  |
              |  +--------------------+  |
              +--------------------------+

GitHub Actions
  lint.yml   -- validation sur chaque PR
  deploy.yml -- build GHCR + deploy sur push main
```

---

## Stack technique

| Composant        | Version    | Role                                         |
|------------------|------------|----------------------------------------------|
| bot-moderation   | Python 3.12 | Moderation automatique, ban, kick            |
| bot-status       | Node.js 20 | Rapport serveur quotidien, statistiques      |
| Terraform        | >= 1.6     | Provisionnement Hetzner Cloud + firewall     |
| Ansible          | >= 2.15    | Configuration OS, securite, deploiement      |
| Prometheus       | 2.48.0     | Collecte de metriques                        |
| Grafana          | 10.2.2     | Visualisation                                |
| Node Exporter    | 1.7.0      | Metriques systeme                            |
| cAdvisor         | 0.47.2     | Metriques par conteneur                      |

---

## Modele de securite

L'acces aux interfaces de monitoring (Prometheus, Grafana, Node Exporter) n'est jamais
expose sur Internet. Ces ports sont lies a l'interface loopback (127.0.0.1) et accessibles
uniquement via un tunnel SSH depuis un poste autorise :

```bash
ssh -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 \
    -p 2222 bot-runner@<SERVER_IP>
```

Le pare-feu Hetzner et UFW appliquent une politique deny-all entrante. Seul le port SSH
(2222) est ouvert, restreint aux adresses IP declarees dans `var.allowed_admin_ips`.

Les tokens Discord et le mot de passe Grafana sont chiffres avec Ansible Vault.
Aucun secret n'apparait en clair dans le depot.

---

## Prerequis

### Poste local

- Terraform >= 1.6.0
- Ansible >= 2.15 avec collections : `community.general`, `community.docker`, `ansible.posix`
- Cle SSH Ed25519 dans `~/.ssh/id_ed25519`

```bash
pip install ansible ansible-lint yamllint
ansible-galaxy collection install community.general community.docker ansible.posix
```

### Comptes

- Compte Hetzner Cloud avec token API
- Deux applications Discord creees sur le portail developpeur
- Depot GitHub avec les secrets suivants :
  - `HCLOUD_TOKEN`
  - `SSH_PRIVATE_KEY`
  - `SERVER_IP`
  - `ANSIBLE_VAULT_PASSWORD`

---

## Deploiement

### 1. Provisionnement Terraform

```bash
cd infra/terraform

terraform init

terraform plan \
  -var="hcloud_token=<TOKEN>" \
  -var="ssh_key_name=<NOM_CLE>" \
  -var="allowed_admin_ips=[\"<VOTRE_IP>/32\"]"

terraform apply \
  -var="hcloud_token=<TOKEN>" \
  -var="ssh_key_name=<NOM_CLE>" \
  -var="allowed_admin_ips=[\"<VOTRE_IP>/32\"]"

terraform output server_ip
```

### 2. Secrets Ansible

```bash
cd infra/ansible/group_vars/all
cp vault.yml.example vault.yml
# Editer vault.yml avec les vrais tokens Discord et le mot de passe Grafana
ansible-vault encrypt vault.yml
```

### 3. Inventaire

Remplacer `{{ server_ip }}` dans `infra/ansible/inventory.ini` par l'IP obtenue via Terraform.

### 4. Premier deploiement

Le premier run utilise le port SSH 22 (avant durcissement). Les suivants utilisent le port 2222.

```bash
cd infra/ansible

# Premier deploiement (port 22, utilisateur root ou deploy)
ansible-playbook -i inventory.ini site.yml \
  --ask-vault-pass \
  -e "ansible_port=22 ansible_user=deploy"

# Deploiements suivants
ansible-playbook -i inventory.ini site.yml --ask-vault-pass
```

### 5. Acces au monitoring

Uniquement via tunnel SSH :

```bash
ssh -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 \
    -p 2222 bot-runner@<SERVER_IP>
```

Grafana disponible sur http://127.0.0.1:3000 (credentials dans vault.yml).

---

## Structure du depot

```
discord-bots-infra/
├── bots/
│   ├── bot-moderation/       # Bot Python, moderation automatique
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── main.py
│   └── bot-status/           # Bot Node.js, statistiques serveur
│       ├── Dockerfile
│       ├── package.json
│       └── index.js
├── infra/
│   ├── terraform/            # Provisionnement Hetzner
│   │   ├── providers.tf
│   │   ├── variables.tf
│   │   ├── main.tf
│   │   └── outputs.tf
│   └── ansible/
│       ├── site.yml          # Playbook principal (5 phases)
│       ├── inventory.ini
│       ├── group_vars/all/
│       │   ├── vars.yml
│       │   └── vault.yml.example
│       └── roles/
│           ├── common/       # Paquets, utilisateur systeme
│           ├── security/     # SSH, UFW, fail2ban, sysctl
│           ├── docker/       # Installation Docker CE
│           ├── bots/         # Deploiement des conteneurs
│           └── monitoring/   # Prometheus, Grafana, exporters
├── monitoring/
│   ├── docker-compose.monitoring.yml
│   └── grafana/provisioning/datasources/prometheus.yml
└── .github/workflows/
    ├── lint.yml              # ansible-lint, terraform, hadolint, yamllint
    └── deploy.yml            # Build GHCR + deploiement Ansible
```

---

## CI/CD

### lint.yml (Pull Requests)

- `ansible-lint` sur tous les playbooks et roles
- `terraform fmt -check` et `terraform validate`
- `hadolint` sur les deux Dockerfiles
- `yamllint` sur l'ensemble des fichiers YAML

### deploy.yml (push sur main)

1. Build des deux images Docker et push sur GitHub Container Registry
2. Connexion SSH au serveur et execution du playbook Ansible avec le tag `bots`
3. Verification du health check de bot-moderation avant de clore le job

---

## Licence

MIT
