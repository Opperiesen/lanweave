# Migration de v0.8.0 vers v0.9.0

La v0.9.0 conserve les formats de configuration, de plan et d’audit de
v0.8.0. Elle ajoute un résultat de convergence post-apply et rend le code de
sortie de `apply` sensible à la preuve disponible après les écritures.

## Changements opérateur

Après un apply qui modifie le contrôleur, Lanweave relit uniquement les
familles concernées :

- `converged` : les écritures correspondent à la configuration déclarée ;
- `drifted` : une différence est prouvée ;
- `uncertain` : la relecture ne permet pas de conclure ;
- `unsupported` : l’adaptateur ne sait pas vérifier la famille.

Un apply convergé garde le code `0`. Un apply dont la relecture prouve un
drift retourne `1`. Une relecture incertaine ou non supportée retourne `2`.
Une erreur d’écriture retourne toujours `2`.

La sortie table ajoute le résumé de convergence. Avec `--output json`, le plan
reste sur stdout et le résultat de convergence est écrit sur stderr. Les
consommateurs qui ne lisaient que stdout continuent donc à recevoir le plan v1.

## Échec partiel

Après un `PlanApplyError`, Lanweave exécute une relecture read-only et ajoute
le résultat sous `convergence` dans le rapport JSON. Il ne rejoue pas la
requête, ne compense aucune écriture et ne fait pas de rollback automatique.

La procédure reste :

```shell
lanweave plan --config config/network.yaml
lanweave apply --config config/network.yaml
```

Il faut examiner le nouveau plan et résoudre toute ambiguïté dans l’interface
UniFi avant d’autoriser une nouvelle mutation. `--prune` reste opt-in.

## Compatibilité

Les configurations v1 et v2, les plans v1 et les résultats d’audit v1 restent
acceptés. Le nouveau schéma est
[`convergence-v1.schema.json`](contracts/convergence-v1.schema.json). Le MCP
reste strictement read-only et aucune nouvelle famille de ressources n’est
introduite.
