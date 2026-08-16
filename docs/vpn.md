# Contrat VPN v0.7.0

Lanweave v0.7.0 ajoute un inventaire VPN local en lecture seule. Le contrat
portable reste volontairement étroit : serveurs VPN, tunnels site-à-site et
routes déclarées pour vérifier les dépendances. Les identifiants du contrôleur,
les clés privées, les clés pré-partagées, les profils générés et les QR codes
ne sont jamais acceptés, exportés ou placés dans un plan.

## Sources contrôleur

Avec une clé de l’Integration API locale, l’adaptateur utilise uniquement les
lectures documentées :

- `GET /v1/sites/{siteId}/vpn/servers` ;
- `GET /v1/sites/{siteId}/vpn/site-to-site-tunnels` ;
- `GET /v1/sites/{siteId}/clients`, filtré sur `VPN` et `TELEPORT` pour les
  pairs actuellement connectés.

Les réponses sont normalisées avant d’être rendues au CLI, à l’export ou au
MCP. Les routes détaillées et les états de handshake ne sont pas fournis par
ces vues officielles ; Lanweave expose donc une couverture
`not-reported-by-official-overview-api` au lieu de déduire une information.

## YAML portable

```yaml
vpn:
  servers:
    - name: Remote Access
      type: wireguard
      enabled: true
  site_to_site_tunnels:
    - name: Branch Office
      type: ipsec
  routes:
    - name: branch-network
      destination: 10.20.0.0/24
      via: Branch Office
      metric: 10
```

`via` doit référencer un serveur ou un tunnel déclaré dans le même document.
Les types VPN restent des chaînes extensibles ; Lanweave ne transforme pas un
type inconnu en protocole supposé.

## Surfaces

- `lanweave vpn --output table|json` lit l’inventaire, les pairs connectés et
  la couverture de télémétrie ;
- `lanweave export` ajoute une section `vpn` sans IDs contrôleur ;
- `lanweave plan` ajoute une observation `read_only.vpn` dans le plan v1 ;
- `lanweave validate` vérifie les routes et leurs dépendances ;
- `lanweave_list_vpn` fournit le même résultat au MCP.

`lanweave apply` refuse un document qui contient une observation VPN en lecture
seule. Il n’existe aucun endpoint d’écriture VPN dans l’adaptateur v0.7.0.
