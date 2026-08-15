# Lanweave v0.5.0 — release notes

Lanweave `v0.5.0` ajoute le firewall local déclaratif comme famille de
ressources indépendante. Cette release conserve le DNS v0.4, les profils, les
capacités d'adaptateur et le MCP strictement en lecture seule.

## Inclus

- zones firewall, groupes d'adresses, groupes de ports et règles ordonnées ;
- modèle portable sans IDs ni payloads contrôleur ;
- validation des références, IP, ports, protocoles, états et actions ;
- inventaire officiel Integration API avec pagination bornée et variantes
  refusées explicitement ;
- export déterministe et secret-free ;
- plans create/update/no-op/delete et `reorder` de première classe ;
- préservation des ressources live non déclarées quand `--prune` est absent ;
- protection des origines système, par défaut et inconnues ;
- analyse visible des règles larges, de l'exposition externe, des ports
  privilégiés et du shadowing exact ;
- confirmation firewall séparée avec `--acknowledge-firewall-risk` ;
- apply API-key local avec phases dépendantes et rapport de récupération
  partielle ;
- surface CLI, capabilities, export et MCP read-only alignée ;
- fixtures et portes d'intégration séparant lecture et mutations autorisées.

## Limites explicites

La release ne couvre pas les mutations session, Site Manager cloud, NAT,
port-forwarding, VPN, groupes non normalisés, endpoints UI non documentés,
rollback automatique ou outils MCP d'écriture. Elle ne déduit jamais une
priorité depuis l'index d'un tableau contrôleur.

La compatibilité publiée est limitée à la matrice testée dans
[`compatibility.md`](compatibility.md). Les deux portes contrôleur de
[`evidence/v0.5.0-firewall.md`](evidence/v0.5.0-firewall.md) doivent être
`passed` avant la publication stable.

## Migration

Le champ `firewall` est optionnel et les configurations existantes restent
valides. Voir [`migration-v0.5.md`](migration-v0.5.md) et
[`firewall.md`](firewall.md) avant de déclarer ou de pruner des règles.

## Vérification

Depuis un checkout propre :

```shell
uv sync --extra dev --extra mcp --locked
uv run python scripts/verify_v050_evidence.py
uv run pytest -m "not integration and not integration_mutation" -q
uv build
```

La release finale ajoute la vérification de l'évidence live, du tag annoté,
des checksums, de la provenance, de GitHub Release et de PyPI.
