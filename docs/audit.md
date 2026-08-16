# Audit de drift v0.8.0

`lanweave audit` compare une configuration déclarative locale avec l’état
portable lu sur le contrôleur sélectionné. L’opération est strictement en
lecture seule : elle ne crée, ne modifie et ne supprime aucune ressource.

## Utilisation

```shell
uv run lanweave audit --config examples/network.yaml --output table
uv run lanweave audit --config examples/network.yaml --output json > audit.json
```

Le format JSON est versionné par `format_version: 1` dans
[`contracts/audit-v1.schema.json`](contracts/audit-v1.schema.json). Il contient
la cible non secrète, les capacités de l’adaptateur, un état global, un résumé
par état et une entrée par famille de ressources.

Les codes de sortie sont conçus pour la CI :

| Code | État | Signification |
| ---: | --- | --- |
| `0` | `in-sync` | Toutes les observations couvertes correspondent à la déclaration |
| `1` | `drifted` | Un écart est prouvé sur une ressource couverte |
| `2` | `unknown` ou `unsupported` | La conclusion ne peut pas être établie, ou l’adaptateur ne couvre pas une section déclarée |

Un échec de configuration, d’authentification ou de lecture contrôleur utilise
également le code `2`. `unknown` ne doit jamais être traité comme un drift
prouvé.

## Périmètre et sémantique

Les réseaux et WLAN sont toujours dans le rapport. Les sections `dns`,
`firewall`, `nat` et `vpn` ne sont comparées que lorsqu’elles sont présentes
explicitement dans le fichier de configuration. Une section explicite mais
non prise en charge produit `unsupported`, sans tentative d’appel hors
capacité.

La comparaison est déterministe :

- les familles et collections sont triées selon leur identité stable ;
- les valeurs par défaut documentées sont normalisées avant comparaison ;
- un drift expose uniquement le nom de la ressource et les chemins de champs
  modifiés, jamais les valeurs sensibles ;
- les identifiants, payloads bruts, mots de passe, références d’environnement,
  clés et tokens sont absents du rapport ;
- un WLAN protégé est comparé comme `credential_managed: true`, sans comparer
  ni exporter sa valeur secrète.

Les identités sont les noms portables, avec `nom + type` pour les entrées DNS.
Les ressources système filtrées par l’export ne deviennent pas des ressources
gérées par l’audit.

## Couverture explicite

Une ressource peut porter `coverage.status: unknown` avec une raison stable :

- `wan_networks_not_reported_by_portable_export` : les réseaux WAN sont
  volontairement exclus de l’export portable ;
- `routes_not_reported_by_official_overview_api` : l’aperçu VPN officiel ne
  fournit pas la table détaillée des routes ;
- `live_observation_failed` ou un code d’adaptateur : la lecture n’a pas permis
  d’établir l’état.

Ces limites sont conservatrices. Le rapport ne transforme pas une absence de
donnée en preuve d’absence.

## Intégration CI

Le résultat JSON peut être archivé comme rapport de conformité tout en
conservant le code de sortie :

```shell
set +e
lanweave audit --config config/network.yaml --output json > audit.json
status=$?
set -e
test "$status" -ne 2 || exit "$status"
exit "$status"
```

La v0.8.0 ne fournit pas de correction automatique et n’élargit pas la surface
de mutation. Après un `drifted`, il faut examiner `lanweave plan` puis appliquer
la procédure de confirmation et de récupération déjà documentée.
