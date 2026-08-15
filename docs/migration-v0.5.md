# Migration de v0.4.0 vers v0.5.0

Lanweave `v0.5.0` conserve les contrats v1/v2 de configuration, le choix
explicite de cible, le plan JSON v1, les réseaux, les WLAN, le DNS local et le
MCP en lecture seule. Le champ `firewall` est optionnel et ne demande aucune
réécriture des fichiers existants.

## Ajouter progressivement le firewall

Commence par une sauvegarde et une lecture live :

```shell
lanweave backup --config config/network.yaml
lanweave export --config config/network.yaml --out exports/live.yaml
```

Ajoute ensuite un bloc `firewall` en gardant les noms de zones et de réseaux
qui existent réellement sur la cible. Le modèle portable est documenté dans
[`firewall.md`](firewall.md), avec un exemple sans ID de contrôleur.

Avant toute mutation :

```shell
lanweave validate --config config/network.yaml
lanweave plan --config config/network.yaml --output json
```

Le premier apply doit rester sans `--prune`. Les opérations `reorder`, les
avertissements de portée et les suppressions éventuelles doivent être revus
séparément. Une règle désactivée peut servir de première validation sur une
cible dédiée.

## Authentification

Le firewall v0.5 utilise la clé API locale et l'Integration API officielle.
Les sessions username/password conservent leurs capacités v0.4 pour les
réseaux et WLAN, mais ne déclarent pas de capacité firewall. Le profil cloud
Site Manager ne gagne aucune capacité firewall par cette migration.

Ne place jamais la clé dans YAML, une issue, un plan, un fixture ou une
commande. Utilise l'environnement ou le gestionnaire de secrets déjà prévu
par le profil sélectionné.

## Ownership et prune

L'export exclut les IDs, les métadonnées d'origine et les groupes/règles
système. La planification protège les origines `SYSTEM_DEFINED`, `DEFAULT` et
inconnues. `--prune` reste opt-in et ne peut supprimer que les ressources
portant une origine utilisateur explicite.

Sans `--prune`, une règle utilisateur non déclarée est conservée et son ordre
est préservé lors d'un reorder déclaré. Pour prendre la responsabilité d'une
politique complète, exporte d'abord l'état supporté, relis-le, puis modifie le
fichier obtenu.

## Retour arrière manuel

Il n'y a pas de rollback automatique. Si l'application s'arrête, considère la
requête en échec comme incertaine, relis le contrôleur et produis un nouveau
plan. Ne relance pas un ancien JSON et n'ajoute pas `--prune` comme raccourci
de récupération. Les détails sont dans [`recovery.md`](recovery.md).
