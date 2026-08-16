# Migration de v0.7.0 vers v0.8.0

La migration est additive. Les configurations v1/v2, les plans JSON v1 et le
contrat MCP v3 restent valides. Aucun champ existant n’est réinterprété et
aucune mutation n’est activée par la mise à jour.

## Nouveautés

- commande `lanweave audit` pour comparer une déclaration et l’état portable ;
- format de rapport [`audit-v1.schema.json`](contracts/audit-v1.schema.json) ;
- outil MCP read-only `lanweave_audit_config` ;
- états et codes CI documentés dans [audit.md](audit.md).

Exemples :

```shell
uv tool install --upgrade lanweave==0.8.0
lanweave audit --config config/network.yaml --output table
lanweave audit --config config/network.yaml --output json > audit.json
```

Les sections `dns`, `firewall`, `nat` et `vpn` restent optionnelles. Si une
section est présente mais que l’adaptateur sélectionné ne sait pas l’exporter,
le résultat est `unsupported` et le code de sortie est `2`. Il ne faut pas
convertir cet état en succès silencieux.

Pour intégrer l’audit sans interrompre une CI sur une limite de couverture,
traite séparément les codes `1` et `2`, puis conserve le JSON pour la revue.
Après un drift prouvé, utilise le plan existant et ses confirmations ; v0.8.0
ne corrige rien automatiquement.
