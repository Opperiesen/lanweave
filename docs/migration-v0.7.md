# Migration de v0.6.0 vers v0.7.0

La migration est additive. Les fichiers v1 et v2 existants restent valides ;
aucune migration automatique n’est nécessaire.

Pour commencer à documenter l’état VPN, ajoute une section `vpn` conforme à
[`vpn.md`](vpn.md) ou utilise `lanweave export` avec une clé d’Integration API
locale. Vérifie ensuite le fichier avec :

```shell
uv run lanweave validate --config examples/vpn.yaml
uv run lanweave vpn --output json
uv run lanweave plan --config examples/vpn.yaml --output json
```

Le plan VPN est une observation et non une autorisation d’écriture. Les
commandes `apply`, les mutations VPN, la génération de profils WireGuard et
la gestion des clés privées restent hors périmètre. Si le contrôleur ne
propose pas les vues officielles VPN, utilise `lanweave capabilities` et
conserve la limitation dans le rapport de compatibilité.
