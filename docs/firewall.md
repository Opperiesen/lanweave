# Firewall déclaratif

Lanweave `v0.5.0` ajoute une famille firewall locale, portable et
explicitement bornée. Le fichier décrit des zones, des groupes d'adresses,
des groupes de ports et des règles ordonnées. Il ne contient jamais les IDs du
contrôleur ni les payloads Integration API.

L'exemple complet se trouve dans [`examples/firewall.yaml`](../examples/firewall.yaml).
Le champ `firewall` est optionnel : les configurations v1 et v2 existantes
restent valides sans migration.

## Modèle portable

```yaml
firewall:
  zones:
    - name: Trusted
      networks: [Home]
  address_groups:
    - name: home-services
      addresses: [192.0.2.10]
  port_groups:
    - name: web
      ports: [443]
  rules:
    - name: allow-web
      order: 100
      placement: after_system_defined
      source:
        zone: Trusted
        address_group: home-services
      destination:
        zone: LAN
        port_group: web
      action: ALLOW
      enabled: true
      ip_version: IPV4
      protocol: TCP
      connection_states: [NEW, ESTABLISHED]
      allow_return_traffic: true
```

Les zones déclarées dans le fichier sont les zones utilisateur que Lanweave
peut gérer. Une règle peut aussi référencer une zone système existante, comme
`LAN` ou `WAN`; son existence et son origine sont vérifiées sur le contrôleur.
Les noms de groupes sont uniques entre groupes d'adresses et groupes de ports.
Les groupes d'adresses restent dans une seule famille IP, et les ports sont
normalisés en nombres ou intervalles bornés.

`order` est un ordre relatif au sein d'une paire zone source/destination et de
son placement. `placement` distingue les règles placées avant ou après les
règles système. Une modification d'ordre apparaît comme une opération
`reorder` distincte ; un tri interne ou un index renvoyé par le contrôleur ne
peut pas changer silencieusement le plan.

Les ressources absentes du fichier ne sont pas supprimées sans `--prune`.
Sans prune, les ressources utilisateur non déclarées et les règles protégées
restent dans l'ordre live. Avec prune, seules les ressources dont l'origine
live est explicitement utilisateur peuvent être supprimées.

## Vérifier et appliquer

```shell
lanweave validate --config config/network.yaml
lanweave capabilities --config config/network.yaml --output json
lanweave export --config config/network.yaml --out live.yaml
lanweave plan --config config/network.yaml --output json
lanweave apply --config config/network.yaml
```

Une règle large, une zone externe, un port privilégié, un risque de shadowing
ou un changement d'ordre produit un avertissement visible. Un apply qui en
contient doit recevoir une seconde autorisation explicite :

```shell
lanweave apply --config config/network.yaml \
  --yes --acknowledge-firewall-risk
```

`--yes` seul ne suffit pas pour contourner ce garde-fou. En mode interactif,
Lanweave demande la chaîne `ACKNOWLEDGE_FIREWALL_RISK` avant la confirmation
normale. MCP peut lire, exporter, valider et planifier ; il ne peut pas
appliquer ou supprimer.

## Compatibilité et limites

Le support v0.5 cible uniquement l'adaptateur `local-classic` avec une clé API
locale et les familles Integration API documentées :

- `firewall/zones` ;
- `traffic-matching-lists` pour les groupes d'adresses et de ports ;
- `firewall/policies` ;
- `firewall/policies/ordering`.

L'authentification session, Site Manager cloud, les variantes de groupes non
normalisées, les endpoints UI non documentés, NAT, port forwarding, VPN et les
outils MCP d'écriture restent hors périmètre. Une réponse malformée, une
origine inconnue ou un ordre impossible à reconstruire fait échouer la lecture
ou le plan au lieu d'être deviné.

## Récupération

L'API n'est pas considérée comme transactionnelle. Après un timeout ou une
erreur ambiguë, le rapport indique les opérations confirmées, incertaines et
non démarrées sans afficher de payload ni de secret. Il faut relire le
contrôleur, générer un nouveau plan et le réexaminer avant de relancer. Voir
[`recovery.md`](recovery.md) et [`migration-v0.5.md`](migration-v0.5.md).
