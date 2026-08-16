# Roadmap v0.8.0 — audit de drift et rapports de conformité

## Objectif

Transformer les exports et observations en un audit déclaratif exploitable par
un opérateur ou une CI, avec une sémantique stable et conservatrice. La
release reste en lecture seule : elle ne déduit pas une autorisation de
mutation et n’ajoute aucun outil MCP d’écriture.

## Décomposition GitHub

1. [#124 — contrat d’audit et sémantique canonique](https://github.com/Opperiesen/lanweave/issues/124)
   - format JSON v1, états `in-sync`, `drifted`, `unknown`, `unsupported` ;
   - identité, valeurs par défaut, tri et frontière de secrets ;
   - distinction entre écart prouvé et couverture insuffisante.
2. [#125 — snapshots live selon les capacités](https://github.com/Opperiesen/lanweave/issues/125)
   - réutilisation de l’export portable secret-free ;
   - pré-vol des capacités avant tout appel ;
   - raisons stables pour les ressources non supportées ou non observables.
3. [#126 — CLI, JSON déterministe et codes CI](https://github.com/Opperiesen/lanweave/issues/126)
   - `lanweave audit --output table|json` ;
   - code `0` pour `in-sync`, `1` pour drift prouvé, `2` pour inconnu/non supporté ;
   - conservation de la sélection de cible v1/v2.
4. [#127 — rapport en lecture seule par MCP](https://github.com/Opperiesen/lanweave/issues/127)
   - `lanweave_audit_config` ;
   - même contrat de cible, capacités, redaction et erreurs que la CLI ;
   - aucune mutation indirecte.
5. [#128 — fixtures, migration et gates](https://github.com/Opperiesen/lanweave/issues/128)
   - fixtures `in-sync`, `drifted`, `unknown` et `unsupported` ;
   - documentation de migration et de compatibilité ;
   - gate hors ligne, tests, build, provenance et publication.

## Gates de release

- `v0.8.0a1` : contrat JSON, canonisation et fixtures de résultat ;
- `v0.8.0b1` : audit CLI et MCP sur les capacités locales existantes ;
- `v0.8.0rc1` : redaction, rapports déterministes, documentation et gate hors ligne ;
- `v0.8.0` : CI complète, tag annoté, artefacts reproductibles, provenance,
  publication PyPI et GitHub Release vérifiées.

## Limites assumées

L’audit ne couvre pas les réseaux WAN exclus de l’export portable et ne prétend
pas observer les routes VPN détaillées lorsque l’API officielle ne les expose
pas. Ces cas sont `unknown`. Les mutations, la correction automatique, le
rollback automatique, l’agrégation multi-contrôleurs et le cloud Site Manager
restent hors périmètre.
