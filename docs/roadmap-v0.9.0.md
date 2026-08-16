# Roadmap v0.9.0 — convergence post-apply et durcissement opérationnel

La v0.9.0 transforme l’application déclarative en boucle opérable :
préparer, appliquer une seule fois, relire l’état affecté et rendre explicite
ce qui est prouvé ou impossible à conclure. Elle s’appuie sur les familles
réseau, WLAN, DNS, firewall et NAT déjà publiées ; elle ne promet ni
transaction, ni compensation, ni rollback automatique.

## Objectif produit

Après une commande `apply`, un opérateur doit pouvoir répondre sans inspecter
le code à trois questions :

1. les familles modifiées correspondent-elles à l’état déclaré ?
2. si une requête a échoué, qu’est-ce qui est confirmé, incertain ou non
   démarré ?
3. quelle est la prochaine action sûre avant une nouvelle tentative ?

## Contrat de convergence

Le résultat JSON v1 est défini par
[`contracts/convergence-v1.schema.json`](contracts/convergence-v1.schema.json).
Il est additif aux formats de configuration, de plan et d’audit existants.

Chaque résultat contient :

- `state`: `converged`, `drifted`, `uncertain` ou `unsupported` ;
- `plan_summary`: le résumé du plan effectivement vérifié ;
- `affected_resources`: uniquement les familles modifiées ;
- `resources`: comptes, findings et raisons de couverture sans payload ni ID ;
- `recovery`: instructions déterministes adaptées à l’état observé.

La priorité globale est conservatrice : `uncertain` domine
`unsupported`, qui domine `drifted`, qui domine `converged`. Une absence de
preuve n’est donc jamais présentée comme une convergence.

## Décomposition de livraison

### 1. Contrat et sélection du périmètre

- introduire le format convergence v1 et ses états stables ;
- dériver les familles affectées à partir des diffs du plan ;
- étendre l’export/audit avec un readback sélectif ;
- garder le MCP strictement en lecture seule.

### 2. Vérification après succès

- relire les familles affectées après la dernière écriture ;
- produire un rapport `converged`, `drifted`, `uncertain` ou `unsupported` ;
- conserver les sorties de plan existantes et écrire le résultat JSON séparé
  sur stderr pour ne pas casser les consommateurs du plan v1 ;
- retourner `0` pour converged, `1` pour drifted et `2` pour les états
  inconclusifs.

### 3. Vérification après échec partiel

- relire sans retry ni mutation après un `PlanApplyError` ;
- inclure la preuve de convergence sous `convergence` dans le rapport de
  récupération JSON ;
- conserver les faits déjà établis (`confirmed_completed`, requête
  incertaine, opérations non démarrées) ;
- rappeler systématiquement qu’un nouveau plan est requis.

### 4. Couverture et tests

- couvrir les plans mono- et multi-familles ;
- injecter des erreurs de lecture, des dérives prouvées et des capacités
  absentes ;
- vérifier les opérations multi-requêtes WLAN et les ressources firewall/NAT ;
- vérifier l’absence de secrets, payloads, réponses brutes et IDs dans les
  rapports ;
- conserver des fixtures hors ligne et ne pas élargir la suite de mutations
  live.

### 5. Documentation et release

- documenter le contrat, les codes CLI et le parcours de récupération ;
- publier une note de migration v0.8 → v0.9 ;
- mettre à jour la matrice de compatibilité et les gates de release ;
- vérifier wheel, sdist, installation propre, tag annoté, checksums,
  provenance, GitHub Release, publication PyPI et attestations ;
- clôturer les issues enfants puis le milestone v0.9.0.

## Limites explicites

- aucun retry automatique, même après un timeout ;
- aucun rollback automatique ou mécanisme compensatoire ;
- aucune écriture MCP ;
- aucune nouvelle famille de ressources ;
- une convergence `unsupported` ou `uncertain` n’est pas un succès ;
- les routes VPN restent hors du périmètre d’application et ne deviennent pas
  vérifiables par ce milestone.

## Gates de sortie

La release n’est prête que si :

1. le contrat convergence v1 et son schéma sont testés ;
2. `apply` vérifie les familles affectées après succès et après échec partiel ;
3. les codes de sortie et les flux stdout/stderr sont documentés et testés ;
4. les fixtures prouvent `converged`, `drifted`, `uncertain` et `unsupported` ;
5. la suite hors ligne complète, ruff et les contrôles de sécurité passent ;
6. les docs de récupération et de migration sont cohérentes avec le code ;
7. la release est issue d’un tag annoté `v0.9.0` et tous les artefacts sont
   vérifiés après publication.

La v1.0.0 ne démarre qu’après fermeture de ce périmètre et un audit des
contrats publics restants.
