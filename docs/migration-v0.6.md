# Migration de v0.5.0 vers v0.6.0

Lanweave `v0.6.0` conserve les contrats v1/v2 de configuration, le choix
explicite de cible, le plan JSON v1 et le MCP strictement en lecture seule. Le
champ `nat` est optionnel et ne demande aucune réécriture des configurations
existantes.

## Ajouter progressivement le NAT

Commence par une sauvegarde et une lecture live :

```shell
lanweave backup --config config/network.yaml
lanweave export --config config/network.yaml --out exports/live.yaml
```

Ajoute ensuite un bloc `nat` avec un nom stable, une interface publique, une
source explicite, un service privé et des plages de ports de même longueur.
Le contrat portable complet et les variantes refusées sont documentés dans
[`nat.md`](nat.md).

Avant toute mutation :

```shell
lanweave validate --config config/network.yaml
lanweave plan --config config/network.yaml --output json
```

Un plan NAT exposé sur le WAN, large, privilégié ou dépendant d'un firewall
non prouvé reste bloqué sans `--acknowledge-risk`. Le premier apply doit rester
sans `--prune`; les suppressions sont relues et confirmées séparément.

## Limites d'authentification et de payload

La v0.6.0 publie uniquement l'adaptateur `local-classic` avec authentification
session pour les mutations NAT. Le sous-ensemble d'écriture prouvé est IPv4,
sans adresse publique explicite, zone source, description, hairpin explicite
ou plusieurs adresses source. L'API-key, Site Manager cloud et les variantes
non prouvées échouent explicitement avant mutation.

Ne place jamais de secret dans YAML, un plan, une issue, un fixture ou une
commande. Utilise l'environnement ou le gestionnaire de secrets du profil.

## Ownership, prune et récupération

L'export supprime les IDs et origines du contrôleur. La planification protège
les origines `SYSTEM_DEFINED`, `DEFAULT` et inconnues; `--prune` ne cible que
les mappings avec une origine utilisateur explicite. L'endpoint classic ne
retournant pas toujours cette origine, un mapping créé est reconnu comme
session-owned uniquement jusqu'à la fin du client courant; une nouvelle
invocation le protège jusqu'à une preuve indépendante.

Il n'y a pas de rollback automatique. Après timeout ou échec partiel, relis
l'inventaire, produis un plan neuf et ne rejoue pas un ancien JSON. Le détail
est dans [`recovery.md`](recovery.md).

Le MCP reste limité à l'inventaire/export, la validation et la planification.
Aucun outil d'apply ou de suppression NAT n'est ajouté.
