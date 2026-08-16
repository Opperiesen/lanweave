# Roadmap v0.7.0 — ressources VPN locales sûres

## Objectif

Livrer un contrat VPN local utile immédiatement pour l’audit et l’export,
capable de servir de base aux futures écritures, sans exposer de secrets ni
activer de mutation non prouvée.

## Décomposition

1. **#118 — contrat portable et frontière de secrets**
   - section `vpn` additive dans les schémas v1/v2 ;
   - serveurs, tunnels et routes avec validation des dépendances ;
   - rejet des clés privées, clés pré-partagées, profils et QR codes.
2. **#121 — inventaire local et fixtures versionnées**
   - Integration API officielle pour les serveurs et tunnels ;
   - pairs `VPN`/`TELEPORT` dérivés des clients connectés ;
   - fixtures supported, empty et malformed avec pagination bornée.
3. **#116 — santé, pairs, routes et dépendances**
   - résumé de santé honnête `inventory-only` ;
   - couverture explicite lorsque les routes/handshakes ne sont pas rapportés ;
   - vérification des références `via` avant toute observation de plan.
4. **#122 — export et migration**
   - export sans IDs, payloads bruts ni secrets ;
   - migration additive v0.6 → v0.7 ;
   - documentation de compatibilité et de récupération.
5. **#114 — CLI et MCP**
   - `lanweave vpn --output table|json` ;
   - `lanweave_list_vpn` ;
   - observation `read_only.vpn` dans le plan v1 ;
   - aucune fonction MCP d’écriture.
6. **#115 — preuves et release gates**
   - tests unitaires, fixtures et gate offline ;
   - vérification de l’absence de secrets ;
   - limitation live documentée pour le contrôleur de référence ;
   - tag/version/artefacts/provenance et publication vérifiés.

## Gates

- `v0.7.0a1` : contrat, validation et fixtures ;
- `v0.7.0b1` : adaptateur, export, plan observation, CLI et MCP ;
- `v0.7.0rc1` : redaction, migration, compatibilité et gate offline ;
- `v0.7.0` : suite complète, tag annoté, artefacts reproductibles et release.

## Limites assumées

La release ne configure pas un VPN. Elle n’accepte ni ne génère de clé
privée, profil client, QR code ou route appliquée. Les écritures et l’audit de
drift généralisé sont reportés aux milestones v0.8.0 et v0.9.0.
