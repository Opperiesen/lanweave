# Lanweave v0.6.0 — release notes

Lanweave `v0.6.0` ajoute la famille NAT et port-forwarding locale comme
extension déclarative indépendante. La release conserve les réseaux, WLAN,
DNS, firewall, profils, capacités d'adaptateur et MCP strictement en lecture
seule.

## Inclus

- contrat portable de mappings NAT sans IDs ni payloads contrôleur;
- inventaire local-classic session et fixtures versionnés;
- export secret-free qui exclut les mappings système et inconnus;
- validation des interfaces, sources, familles IP, protocoles, ports et
  références réseau;
- analyse d'exposition, de conflits et de dépendances firewall;
- plans déterministes avec create/update/no-op/delete et origines protégées;
- apply et prune contrôlés pour le sous-ensemble IPv4 local prouvé;
- ownership de session explicite pour les créations classic dont l'endpoint ne
  renvoie pas de métadonnée d'origine;
- rapport de récupération partielle avec opération incertaine et plan neuf;
- capacités CLI et réponses MCP de validation/export/plan alignées;
- migration, compatibilité, sécurité, récupération et preuves protégées dédiées.

## Limites explicites

Les mutations NAT API-key, cloud, VPN, endpoints UI non documentés, IPv6,
adresses publiques explicites, zones source, descriptions, hairpin explicite,
sources multiples, rollback automatique et outils MCP d'écriture ne font pas
partie de cette release. Une variante non prouvée est rejetée plutôt que
convertie silencieusement. Une nouvelle exécution protège également les
mappings classic sans origine au lieu de les considérer comme gérés.

La compatibilité publiée est limitée à la matrice testée dans
[`compatibility.md`](compatibility.md). Les preuves contrôleur et les gates de
publication sont détaillées dans
[`evidence/v0.6.0-nat.md`](evidence/v0.6.0-nat.md).

## Migration et vérification

Le champ `nat` est optionnel; les fichiers v1/v2 existants restent valides.
Voir [`migration-v0.6.md`](migration-v0.6.md) et [`nat.md`](nat.md) avant de
déclarer ou de pruner un mapping.

Depuis un checkout propre :

```shell
uv sync --extra dev --extra mcp --locked
uv run python scripts/verify_v060_evidence.py
uv run pytest -m "not integration and not integration_mutation" -q
uv build
```

La release ajoute la vérification du tag annoté, de la version projet, des
checksums, de la provenance, de GitHub Release, de PyPI et des attestations.
