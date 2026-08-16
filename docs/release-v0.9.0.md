# Lanweave v0.9.0

La v0.9.0 ajoute la vérification de convergence après application et renforce
la récupération opérateur après une défaillance partielle.

## Fonctionnalités

- format convergence v1, versionné et documenté ;
- readback ciblé des familles modifiées après un apply réussi ;
- états explicites `converged`, `drifted`, `uncertain` et `unsupported` ;
- preuve de convergence ajoutée aux rapports d’échec partiel ;
- codes CLI cohérents avec la preuve (`0`, `1`, `2`) ;
- rapport limité aux noms, comptes, findings et raisons de couverture ;
- aucune écriture MCP, aucun retry automatique et aucun rollback automatique.

## Vérification

Avant publication, la CI doit vérifier la suite hors ligne complète, ruff,
les contrats JSON, l’absence de secrets dans les rapports, l’installation
propre des artefacts, le tag annoté, les checksums, la provenance et la
publication PyPI via Trusted Publishing.

La procédure d’installation et de vérification générale est décrite dans
[`release.md`](release.md). La procédure de récupération est décrite dans
[`recovery.md`](recovery.md) et la migration dans
[`migration-v0.9.md`](migration-v0.9.md).
