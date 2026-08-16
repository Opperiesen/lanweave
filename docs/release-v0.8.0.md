# Lanweave v0.8.0

v0.8.0 ajoute un audit de drift déclaratif, déterministe et conservateur pour
les ressources portables Lanweave.

## Inclus

- contrat JSON d’audit v1 ;
- comparaison secret-free des réseaux, WLAN, DNS, firewall, NAT et VPN selon
  les capacités de l’adaptateur ;
- états `in-sync`, `drifted`, `unknown` et `unsupported` ;
- codes de sortie CI `0/1/2` ;
- commande CLI `lanweave audit` en tableau ou JSON ;
- outil MCP read-only `lanweave_audit_config` ;
- fixtures, documentation de migration et gate hors ligne ;
- aucune extension de la surface de mutation.

## Limites

Les réseaux WAN ne sont pas inclus dans l’export portable et les routes VPN
détaillées ne sont pas rapportées par l’aperçu officiel utilisé par Lanweave.
Ces éléments sont marqués `unknown`, jamais comme conformes ou absents. Le
cloud Site Manager reste limité à ses capacités documentées et renvoie
`unsupported` pour les ressources non exposées.

## Preuves

- gate d’audit hors ligne : passé dans
  [`scripts/verify_v080_evidence.py`](../scripts/verify_v080_evidence.py) ;
- tests unitaires, CLI, MCP, contrat et build : exécutés par la CI ;
- aucune preuve live supplémentaire n’est nécessaire pour cette release : le
  contrat v0.8.0 publie explicitement ses limites de couverture.
