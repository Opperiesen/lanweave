# Lanweave v0.7.0

v0.7.0 ajoute le premier contrat VPN local, en lecture seule et sans secrets.

## Inclus

- inventaire des serveurs VPN et tunnels site-à-site via l’Integration API ;
- pairs VPN/Teleport actuellement connectés ;
- validation des routes et des dépendances `via` ;
- export YAML sans IDs contrôleur, clés ou profils générés ;
- observation VPN redacted dans le plan JSON v1 ;
- commandes `lanweave vpn` et `lanweave_list_vpn` ;
- capacités locales API-key `read/export/plan` ;
- fixtures, tests et gate de preuve hors ligne.

## Exclusions explicites

Les mutations VPN, la génération de clés ou de profils, les QR codes, les
routes réellement appliquées et les écritures MCP ne font pas partie de cette
release. Les routes détaillées et les handshakes ne sont pas inventés lorsqu’ils
ne figurent pas dans l’API officielle.

## Preuves

- Gate offline v0.7 : passé dans `scripts/verify_v070_evidence.py` ;
- preuve live VPN : limitation documentée, car le contrôleur de référence ne
  fournit pas de configuration VPN active à vérifier dans ce cycle.

Le tag, la version du paquet, les artefacts, l’installation propre, la
provenance et la publication suivent les mêmes protections que les releases
précédentes.
