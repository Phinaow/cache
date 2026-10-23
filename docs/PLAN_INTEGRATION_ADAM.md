# Project Plan: intégration du cache DRAM dans un clone propre d’ADAM

## Overview

Ce plan décrit l’ajout de la version actuelle du cache de `/home/johann/cache` dans un **nouveau clone propre d’ADAM**, que l’utilisateur préparera. Il s’appuie sur l’analyse en lecture seule des modifications non commitées de `/home/johann/quick_test/adam`. Le dépôt ancien sert de référence pour comprendre les raccordements ; il ne sera pas la base de travail de l’intégration. La réussite exige un chemin fonctionnel depuis les maîtres du SoC jusqu’à la DDR3, une validation en simulation, une fermeture physique Vivado et des essais sur Nexys Video avec un bitstream identifié.

Document établi le 22 octobre 2026. Il constitue le plan historique antérieur
à l’implémentation et ne décrit plus l’état courant. L’intégration a depuis été
réalisée, routée et validée sur carte. Pour reprendre le travail, utiliser
[ADAM_INTEGRATION_HANDOFF.md](ADAM_INTEGRATION_HANDOFF.md) et les preuves sous
`adam/docs/`.

Mise à jour après autorisation d’implémentation : une première intégration RTL est
maintenant présente dans le clone local `../adam/`. Les résultats réellement
obtenus et les tâches restantes sont dans
[DRAM_INTEGRATION.md](../adam/docs/DRAM_INTEGRATION.md). Ce plan conserve les
jalons de la migration complète ; sa présence ne signifie pas qu’ils sont tous clos.

### Références et origine des informations

- ADAM examiné : `/home/johann/quick_test/adam` ; commit HEAD `785333c9908751c419ff4d553b8b68c280c4771a`.
- Sources étudiées : différences non commitées des fichiers suivis, fichiers non suivis et différences internes aux sous-modules.
- Cache à importer : fichiers actuels de ce workspace, dont beaucoup sont modifiés ou non suivis. Un commit Git seul ne suffit donc pas à identifier cette version : relever également les empreintes des fichiers effectivement importés.
- Contrat : [CACHE_CONTRACT.md](CACHE_CONTRACT.md).
- Architecture : [MODULES.md](MODULES.md).
- Preuves et limites du cache autonome : [VERIFICATION_STATUS.md](VERIFICATION_STATUS.md).
- Construction et essais physiques de référence : [BOARD_TEST.md](BOARD_TEST.md).

Les différences Git révèlent les changements réalisés, mais pas leur chronologie exacte ni la nécessité de chaque correctif de dépendance. L’ordre ci-dessous est un ordre de reconstruction fondé sur les dépendances techniques.

### Ce qui avait été fait pour l’ancienne intégration

| Couche | Modifications observées | Rôle à reproduire |
|---|---|---|
| Configuration Python | Ajout de `en_hsext`, `mmap_hsext` et réduction de la borne de `mmap_mem` | Déclarer une destination externe configurable sans chevauchement |
| Configuration générée | Extension de `adam_cfg_pkg.sv.j2`, `cfg/adam_cfg.h.j2` et `include/adam/macros.svh` | Propager les paramètres au RTL et au logiciel |
| Fabric haute vitesse | Nouveau port `hsext`, destination supplémentaire, règle de décodage et translation d’adresse | Router les requêtes vers le cache |
| Hiérarchie SoC | Ports ajoutés à `adam_fabric`, `adam` et `adam_top` | Exposer le bus au niveau carte |
| Cache | Dix sources non suivies sous `rtl/dram/`, ajoutées à `rtl/CMakeLists.txt` | Fournir le cache et l’accès MIG |
| Top carte | Ports DDR3, bus AXI-Lite et instance `cache_axi` | Raccorder le SoC au sous-système mémoire |
| IP et construction | Nouveau clock wizard, IP RAM et appels Tcl dans la cible Nexys Video | Générer le matériel physique |
| Logiciel | Région linker HSEXT, pointeur RAL et application TFLM utilisant la DDR | Rendre la mémoire utilisable par les programmes |

Les fichiers `ips/mig/mig.tcl`, `mig.prj` et `mig.xdc` sont déjà suivis dans le commit ADAM examiné. L’ancien diff les raccorde à la cible ; il ne les crée pas. Le futur clone devra être vérifié sur ce point.

### Architecture visée

Le chemin conservé sera : maîtres ADAM → fabric AXI-Lite haute vitesse → HSEXT avec soustraction de base → `adam` → `adam_top` → sous-système cache → MIG → DDR3.

L’orientation retenue pour le plan est de créer une façade ADAM `cache_axi` mince autour de `top_cache`, lequel instancie `cache_core` et le MIG. Cela conserve les noms d’interfaces connus de l’intégration ancienne tout en utilisant la nouvelle séparation du cache. La façade ne dupliquera ni les moteurs, ni les CDC, ni le contrôleur MIG. Son utilité sera confirmée lors de la revue des ports du nouveau clone ; une instance directe de `top_cache` reste possible si elle simplifie réellement le raccordement.

Configuration initiale proposée : cache bloquant entièrement associatif de 8 Kio, huit lignes de 1 Kio, CPU AXI-Lite 32 bits, mémoire AXI 128 bits, DDR3 512 Mio. Le backend RTL sera utilisé en premier. La sélection `USE_VENDOR_RAM` restera disponible ; la validation de la variante IP sera distincte.

Le démonstrateur UART autonome du cache n’est pas importé dans le produit ADAM. Les essais système utiliseront les interfaces et le logiciel d’ADAM.

### Mapping mémoire proposé

| Usage | Adresses globales ADAM | Adresses locales transmises au cache |
|---|---|---|
| DDR de 512 Mio | `[0x50000000, 0x70000000[` | `[0x00000000, 0x20000000[` |
| Ancienne extension de fenêtre | `[0x70000000, 0x80000000[` | `[0x20000000, 0x30000000[` |

La macro `ADAM_AXIL_OFFSET` soustrait déjà la base HSEXT dans la fabric. Exemple : `0x50001000` devient `0x00001000`. Aucune seconde translation ne doit être ajoutée dans la façade ou le cache.

L’ancien `transaction.sv` détourne le bit 29 de l’adresse locale pour fournir des compteurs miss/hit et un registre de contrôle. La nouvelle version ne possède pas ces registres. **Proposition initiale : exposer uniquement les 512 Mio physiques comme RAM et différer la télémétrie.** La décision sera prise après recherche de leurs usages. Si leur conservation est nécessaire, réserver un espace de registres distinct, décodé dans une couche ADAM, et définir son protocole indépendamment de la RAM.

Le linker ne doit jamais annoncer 768 Mio de RAM. L’ancienne application utilise `0x50000000` pour l’arène, `0x59000000` pour le modèle et `0x67000000` pour l’entrée : ces trois bases sont dans la DDR physique, sous réserve de vérifier la taille de chaque allocation.

## Phases & Tasks

Efforts relatifs : P = petit, M = moyen, G = grand. Les marqueurs de chemin critique indiquent les tâches structurantes ; les validations sont des critères de passage, pas des options.

### Phase 1: figer la base et le contrat ADAM

**Goal:** disposer d’un clone identifié, de références reproductibles et de décisions d’interface explicites.
**Estimated effort:** M.
**Milestone deliverable:** inventaire de provenance, configuration cible et contrat mémoire/reset approuvés dans la documentation du clone.

| # | Task | Effort | Dependencies | Critical Path? |
|---|---|---|---|---|
| 1.1 | Relever le chemin du clone fourni par l’utilisateur, son commit, ses consignes et les révisions de sous-modules ; comparer sa structure au commit ancien examiné | P | Clone disponible | Oui |
| 1.2 | Identifier la version du cache par un manifeste des sources et SHA256 ; conserver les preuves du cache autonome séparées des futurs résultats ADAM | P | 1.1 | Oui |
| 1.3 | Construire et simuler une configuration ADAM de référence sans DRAM ; relever outils, commandes et défauts préexistants | M | 1.1 | Oui |
| 1.4 | Fixer HSEXT, les registres éventuels, la largeur de bus, le backend initial et la politique d’activation par cible | M | 1.2, 1.3 | Oui |
| 1.5 | Cartographier reset carte, reset SoC, reset cache, lock et calibration ; examiner pause et arrêt d’horloge ainsi que tous les chemins d’accès DDR | M | 1.4 | Oui |

Critères de sortie : mapping sans chevauchement ; contrat des erreurs et resets écrit ; absence de maître contournant le cache démontrée ou stratégie explicitement définie. Si la référence ADAM échoue, caractériser le défaut avant de lui attribuer une cause DRAM.

### Phase 2: créer la destination HSEXT et son banc de vérification

**Goal:** reproduire le raccordement générique du SoC sans dépendre encore d’une DDR physique.
**Estimated effort:** M.
**Milestone deliverable:** accès AXI-Lite routés et translatés correctement vers un esclave de test, avec génération RTL/C cohérente.

| # | Task | Effort | Dependencies | Critical Path? |
|---|---|---|---|---|
| 2.1 | Ajouter les paramètres HSEXT dans `cfg.py`, les deux templates de configuration et `macros.svh` | M | Phase 1 | Oui |
| 2.2 | Ajouter la destination conditionnelle dans `adam_fabric_hsdom` et la propager dans `adam_fabric`, `adam` et `adam_top` | M | 2.1 | Oui |
| 2.3 | Préparer un banc vérifiant décodage, translation, réponses d’erreur, AW/W indépendants et transactions de plusieurs maîtres | M | 1.4, 1.5 | Non |
| 2.4 | Adapter les générateurs linker et RAL pour la seule mémoire disponible ; compiler les fichiers C générés et vérifier les valeurs RTL produites | M | 2.1 | Non |
| 2.5 | Tester HSEXT activé et désactivé, limites de plage et absence de régression des destinations existantes | M | 2.2, 2.3, 2.4 | Oui |

Le port désactivé doit être terminé conformément aux conventions ADAM. Les bancs et autres tops affectés par les nouveaux ports doivent être raccordés explicitement. Ne pas reproduire le point-virgule manquant de l’ancien template C (`bool en_hsext`).

### Phase 3: importer le nouveau cache et vérifier le sous-système

**Goal:** disposer du nouveau cache dans ADAM, indépendant des IP physiques pour la simulation.
**Estimated effort:** M.
**Milestone deliverable:** sous-système cache compilé depuis les sources du clone et tests Cocotb ciblés réussis.

| # | Task | Effort | Dependencies | Critical Path? |
|---|---|---|---|---|
| 3.1 | Importer les sources du manifeste du cœur dans `rtl/dram/`, avec `top_cache` et les documents de contrat/provenance utiles | M | Phase 2 | Oui |
| 3.2 | Adapter les listes CMake : package avant utilisateurs, une définition par module et séparation des sources communes et FPGA | M | 3.1 | Oui |
| 3.3 | Porter les tests Cocotb du cœur, RAM, CDC et moteurs avec leurs auxiliaires ; adapter les chemins et répertoires de construction | M | 3.1 | Non |
| 3.4 | Raccorder la façade `cache_axi` au nouveau `top_cache`, puis vérifier ports, statuts et reset avec un modèle MIG fonctionnel | M | 3.2, 3.3 | Oui |
| 3.5 | Exécuter les tests unitaires affectés puis les intégrations cache ; contrôler le lint brut et documenter chaque avertissement nouveau | M | 3.4 | Oui |

Sources communes à importer depuis `src/cache.f` : `cache_pkg`, `reset_sync`, `cdc_handshake`, `plru`, `transaction`, `hit_detection`, `cache_controller`, `refill_engine`, `writeback_engine`, `miss_handler`, `bl_mem`, `true_dual_port_ram` et `cache_core`. Ajouter `src/top_cache.sv` pour le raccordement MIG.

Ne pas réintroduire `save_controller.sv`, le wrapper Python supprimé ou une dépendance à `generated_config.py`. Les modèles MIG/horloges de test sont exclusivement dans les sources de simulation. Préserver les assertions RTL, les seeds fixes et l’isolation des builds. Adapter l’accès Docker au clone sans recréer par défaut le conteneur existant ni supposer que son montage `/phinaow` contient le nouveau dépôt.

### Phase 4: intégrer les IP, horloges et contraintes physiques

**Goal:** élaborer le top Nexys Video avec les vraies IP et un reset cohérent dans tous les domaines.
**Estimated effort:** G.
**Milestone deliverable:** élaboration/synthèse du top complet réussie, IP uniques et contraintes appliquées aux objets attendus.

| # | Task | Effort | Dependencies | Critical Path? |
|---|---|---|---|---|
| 4.1 | Comparer les configurations MIG et clock wizard ADAM avec celles validées du cache ; fixer fréquences, buffers et polarités de reset | M | Phase 3 | Oui |
| 4.2 | Adapter `adam_nexys_video.sv` : ports DDR3, bus AXI-Lite, horloges, façade et prise en compte du lock | M | 4.1 | Oui |
| 4.3 | Adapter les scripts IP : backend RTL sans ancienne IP RAM ; variante vendor avec IP `cache_ram_ip`, latence et masques conformes | M | 4.1 | Non |
| 4.4 | Ajouter les contraintes CDC des deux mailboxes, adaptées aux fréquences et à la hiérarchie ; vérifier que les sélections ne sont pas vides | M | 4.2 | Oui |
| 4.5 | Mettre à jour la cible CMake Nexys Video et vérifier les autres cibles partageant le top ; synthétiser et contrôler ressources et contraintes | G | 4.2, 4.3, 4.4 | Oui |

Points précis à traiter :

- L’ancien MIG utilise `SystemClock=Single-Ended` malgré une alimentation par clock wizard ; la configuration validée du cache utilise `No Buffer`. Réconcilier configuration, ports et contraintes sans empiler des buffers d’entrée.
- L’ancien clock wizard fournit nominalement CPU 50 MHz, système MIG 100 MHz et référence 200 MHz. Confirmer ces valeurs dans les IP générées ; le domaine mémoire du cache reste `ui_clk` du MIG.
- Le nouveau cœur doit rester en reset jusqu’à disponibilité de la mémoire ; la perte de calibration provoque un reset destructif. Examiner les resets SoC indépendants pour éviter une transaction orpheline après reset d’un seul côté du bus.
- L’ancienne IP RAM s’appelle `true_dual_port_ram`, nom désormais utilisé par le wrapper RTL. Générer uniquement `cache_ram_ip` pour la variante vendor.
- Les faux chemins ne doivent viser que les premiers étages de synchronisation ; conserver les contraintes de délai du payload et de bus skew. Les 10 ns du projet source sont une valeur à justifier avec les horloges retenues.
- Utiliser Vivado sur l’hôte. Aucun modèle fonctionnel de test ne doit entrer dans la synthèse ou le bitstream.

### Phase 5: valider le parcours ADAM complet en simulation

**Goal:** vérifier l’intégration au travers de la fabric et du logiciel, au-delà des tests du cache seul.
**Estimated effort:** G.
**Milestone deliverable:** campagne système reproductible et programme mémoire RISC-V réussis, avec limites consignées.

| # | Task | Effort | Dependencies | Critical Path? |
|---|---|---|---|---|
| 5.1 | Étendre le banc HSEXT au vrai cache avec modèle mémoire AXI indépendant et modèle MIG explicitement fonctionnel | M | Phase 4 | Oui |
| 5.2 | Vérifier données, strobes, évictions sales et erreurs via plusieurs maîtres ; contrôler les pauses et l’ordre des réponses | G | 5.1 | Oui |
| 5.3 | Vérifier reset/démarrage/perte de calibration et limites d’adresses, sans allocation silencieuse dans l’ancienne fenêtre de registres | M | 5.1 | Non |
| 5.4 | Exécuter un programme RISC-V simple depuis la mémoire interne, effectuant des accès DDR sur plus de huit lignes | M | 5.2, 5.3 | Oui |
| 5.5 | Exécuter les régressions ADAM affectées et cache ; établir la matrice des résultats par configuration | M | 5.4 | Oui |

Scénarios obligatoires : première/dernière adresse DDR, première adresse exclue, absence de double translation, mots voisins conservés après écriture partielle, alternance lecture/écriture, réponses bloquées, erreurs R/B et absence d’effet de bord sur accès illégal. Une mémoire de simulation réduite ne prouve pas le comportement des adresses hautes : utiliser une représentation sparse ou un test de décodage adapté.

Le test logiciel initial doit utiliser des lectures réellement effectuées et des écritures visibles, avec oracle indépendant et résultats reproductibles. La transformation BCResNet de l’ancien `tflm_lenet.cpp` est différée : elle servira ensuite de charge représentative, après le test mémoire minimal.

### Phase 6: fermer la validation physique et livrer l’intégration

**Goal:** démontrer le fonctionnement sur Nexys Video et rendre l’ajout reproductible depuis le clone.
**Estimated effort:** G.
**Milestone deliverable:** bitstream identifié, rapports contrôlés, résultats matériels et documentation associés à la même version des sources.

| # | Task | Effort | Dependencies | Critical Path? |
|---|---|---|---|---|
| 6.1 | Placer/router la variante RTL et examiner timing, CDC, DRC, bus skew et inférence BRAM | G | Phase 5 | Oui |
| 6.2 | Vérifier les périphériques puis programmer de façon volatile le bitstream ADAM dans le cadre des essais autorisés | P | 6.1 | Oui |
| 6.3 | Exécuter le test DDR par logiciel ADAM : motifs, accès aléatoires, masques, évictions et adresses hautes ; consigner les zones écrasées | M | 6.2 | Oui |
| 6.4 | Construire et vérifier la variante vendor si retenue dans le périmètre final ; refaire les preuves RAM pertinentes et les essais associés | G | 6.3 | Non |
| 6.5 | Documenter commandes, mapping, limitations et SHA256 ; préparer des commits limités aux sources et documents d’intégration | M | 6.3 et 6.4 si retenue | Oui |

Chaque variante livrée a ses propres preuves. En cas d’adaptation RAM, refaire la vérification d’inférence et l’équivalence XSim contre la vraie IP. Un changement de reset, CDC ou top exige une nouvelle analyse physique. Les résultats du cache autonome ne sont jamais présentés comme des résultats du SoC ADAM.

Ne pas programmer en flash par défaut. L’outil UART du démonstrateur autonome n’est pas supposé compatible avec ADAM. La méthode de chargement, d’exécution et de collecte des résultats devra utiliser le bootloader/debug réellement disponible.

## Critical Path Summary

Le chemin structurant est : référence propre (1.1–1.3) → contrat mémoire/reset (1.4–1.5) → HSEXT vérifié (2.1–2.5) → import et sous-système cache (3.1–3.5) → top/IP/contraintes (4.1–4.5) → simulation système et logiciel (5.1–5.5) → fermeture physique et carte (6.1–6.3) → livraison (6.5).

Un retard sur le mapping ou le reset reporte les raccordements et invalide les tests préparés sur une mauvaise hypothèse. Ces décisions doivent donc précéder l’implémentation. La préparation des bancs peut avancer en parallèle des raccordements une fois leurs interfaces fixées ; les adaptations linker/RAL peuvent avancer après la configuration ; la variante vendor est un travail distinct après validation de la variante RTL. Ces possibilités ne supposent aucune délégation automatique.

Découpage de commits proposé : configuration et générations ; sortie HSEXT et tests ; import du cache et provenance ; top/IP/contraintes ; validation système et logiciel ; résultats physiques et documentation. Chaque commit doit compiler dans son périmètre ou préciser explicitement sa dépendance au précédent.

## Risks & Assumptions

- **Base différente :** le clone peut viser un commit plus récent que l’ADAM examiné. Comparer les interfaces avant de reproduire un changement ; ne pas appliquer aveuglément un ancien patch.
- **Provenance du cache :** les sources validées sont actuellement en partie non commitées. Conserver un manifeste d’empreintes et vérifier l’identité des copies importées.
- **Sous-modules modifiés :** les différences portent sur `axi_lite_demux`, `cf_math_pkg`/ECC, le handshake XIF CV32E40X et `dm_mem`. Leur nécessité pour la DRAM n’est pas démontrée. Les traiter comme correctifs séparés, avec échec reproductible et validation, uniquement si nécessaires.
- **Ancienne configuration trop globale :** `en_hsext=True` était la valeur Python par défaut, alors que le raccordement physique est propre à la cible Nexys Video. Définir explicitement les configurations sans DDR et tester leur désactivation.
- **Ancienne fenêtre de 768 Mio :** ne pas réutiliser sa taille comme capacité RAM. Séparer mémoire et éventuels registres dans le contrat et le linker.
- **Coexistence de maîtres :** plusieurs maîtres derrière le cache commun sont possibles ; un accès direct à la DDR contournant le cache n’est pas cohérent avec les lignes locales. Examiner DMA, debug et chemins de chargement.
- **Reset :** aucune sauvegarde implicite des lignes sales, aucun flush/invalidate de maintenance. Ne pas promettre de conservation après reset ou perte de calibration.
- **Transport bloqué :** le cache ne promet pas de timeout fini si la mémoire ne termine pas une réponse. Les bancs utilisent des attentes bornées pour détecter un blocage sans modifier ce contrat.
- **Couverture :** les modèles MIG et Verilator ne prouvent ni le comportement électrique DDR3 ni tous les effets quatre états. Distinguer simulation, équivalence RAM, rapports physiques et essais carte.
- **Périmètre initial proposé :** cible `nexys_video` avec backend RTL. L’ancienne cible utilise CV32E40P et Ibex ; une cible CV32E40X séparée partage le top et devra au moins être contrôlée pour les effets de bord.
- **Préservation :** l’ancien workspace ADAM reste intact. Ne pas recopier ses changements de formatage, fichiers binaires applicatifs ou dépendances modifiées sans besoin établi.

## Open Questions (if any)

Les décisions suivantes sont à fermer en phase 1 avant les tâches qui en dépendent ; elles n’empêchent pas la préparation du présent plan.

1. Chemin et commit du clone propre fourni par l’utilisateur ; conservera-t-il la cible CPU de référence ou une autre variante ?
2. Confirmer la proposition d’une fenêtre RAM de 512 Mio sans les anciens registres de statistiques, ou préciser les usages qui exigent leur conservation.
3. La livraison initiale doit-elle inclure seulement le backend RTL, ou également une variante IP entièrement validée ?
4. Quel mécanisme ADAM sera utilisé pour charger et exécuter le test matériel, et quels resets indépendants doivent être supportés ? Le choix sera fondé sur la configuration effective du clone.
