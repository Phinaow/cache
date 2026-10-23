# Project Plan: finalisation du cache FPGA

## Overview

Objectif : livrer un cache entièrement associatif, write-back et write-allocate, avec interface processeur de type AXI4-Lite 32 bits, interface mémoire AXI4 128 bits, domaines d’horloge distincts, et RAM sélectionnable à l’élaboration entre description RTL et IP Vivado. La référence actuelle est 8 Kio, 8 lignes de 1 Kio, mémoire externe de 512 Mio. La cible du projet Vivado est une Nexys Video / Artix-7 xc7a200tsbg484-1. Le résultat attendu comprend RTL, tests reproductibles, assertions, scripts de construction, rapports CDC/timing/ressources et procédure de validation sur carte.

Ce document est un audit statique et un plan d’exécution, pas une certification du matériel. Aucune correction RTL n’a été appliquée pendant sa rédaction. Les changements locaux préexistants dans generated_config.py, test/conftest.py, src/bl_mem.sv et test/test_bl_mem.py sont conservés. Les constats de simulation restent à confirmer avec un environnement fonctionnel.

### Vérifications réalisées

- Lecture des modules du cœur, du stockage, des moteurs DDR, du CDC, des tests, des pilotes/modèles Python et des sources UART/Vivado utiles à l’intégration.
- Analyse syntaxique Python : erreur confirmée dans test/test_bl_mem.py:80, affectation inachevée.
- Lint de top_cache avec Verilator local 5.020, sans les exemptions : élaboration terminée avec avertissements, dont largeurs dans writeback_engine, signaux d’erreur inutilisés et sorties non pilotées des déclarations IP. Ces sorties non pilotées sont attendues pour des déclarations d’IP ; elles ne prouvent pas une erreur du circuit généré par Vivado.
- Lint du top uart_to_cache : échec confirmé sur le port .led absent de top_cache ; avertissements de signaux implicites led dans uart_to_axi et cycle_ct dans uart_to_cache.
- Cocotb et pytest absents du Python système consulté ; simulations non exécutées. Le Dockerfile prévoit Verilator 5.046 et Cocotb 2.0.1 : les résultats locaux de lint ne remplacent pas la validation avec ces versions.
- Pas de synthèse ni d’implémentation Vivado exécutées ; l’inférence BRAM, les collisions RAM, la métastabilité et le timing ne sont pas validés.

### Priorités et lecture des constats

P0 : corruption, interblocage, violation de protocole ou impossibilité de vérifier/construire. P1 : robustesse et intégration nécessaires à la livraison. P2 : maintenabilité ou optimisation après correction fonctionnelle.

« Confirmé » désigne un comportement directement visible dans les sources ou un contrôle exécuté. « Risque » désigne une conséquence à reproduire par test, analyse temporelle ou synthèse. Les localisations correspondent à l’état du dépôt audité.

### Registre des problèmes

| ID | Priorité / statut | Localisation | Problème et conséquence | Traitement |
|---|---|---|---|---|
| A01 | P0 confirmé | transaction.sv:152,167 | RVALID n’est émis que si RREADY est déjà à 1. Un maître qui attend RVALID pour présenter RREADY peut bloquer. | Réponse enregistrée indépendante de READY ; tâche T12. |
| A02 | P0 confirmé | transaction.sv:202–224 | BVALID peut apparaître combinatoirement pendant le handshake W, avant son achèvement au front ; chemins entrée-sortie combinatoires AXI. | Enregistrer réception AW/W et produire B ensuite ; T12. |
| A03 | P0 risque fort | transaction.sv:91–95,148–169 | RDATA est branché directement sur une RAM synchrone ; hit et changement de voie ne constituent pas une preuve que la donnée RAM est disponible. Lecture immédiate après refill ou changement de ligne susceptible de retourner l’ancien mot. | États explicites demande RAM / attente / réponse et capture ; T12, T24. |
| A04 | P0 confirmé | transaction.sv:79–95,135,187 | Les adresses hors plage ou désalignées produisent SLVERR mais continuent vers recherche, refill et écriture RAM. Une adresse hors plage partage les bits bas d’une adresse valide. | Rejeter avant toute opération sur cache/DDR ; consommer les canaux requis sans effet de bord ; T12. |
| A05 | P1 confirmé | hit_detection.sv:202–203 | complete_access est remis à zéro lors des miss seulement. Après un premier hit notifié au PLRU, les hits suivants peuvent ne plus actualiser le remplacement. | Notification par transaction achevée, avec consommation unique ; T14. |
| A06 | P1 confirmé | hit_detection.sv:230 | dirty est positionné sur awvalid interne et hit, avant la modification effective, même si WSTRB vaut zéro. | Événement explicite de commit d’écriture et masque non nul ; T14. |
| A07 | P0 risque | hit_detection.sv:73,118–120,212,234 | Voie victime et adresse du miss non figées localement ; lru_way reste actualisable pendant une opération. La stabilité dépend implicitement de transaction et du pipeline PLRU. | Capturer contexte et victime une seule fois, maintenir jusqu’à fin ; T14. |
| A08 | P0 confirmé | plru.sv, bloc always_ff final | access_ready_o n’est pas initialisé dans la branche reset. Simulation 2 états susceptible de cacher le défaut. | Initialiser toutes les sorties de contrôle ; T13. |
| A09 | P0 risque fort | plru.sv, pipeline q.valid | Un nouvel accès peut être accepté tous les deux cycles ; l’actualisation de l’arbre utilise des nœuds enregistrés et la variable access courante. Celle-ci peut déjà contenir l’accès suivant. | Simplifier la mise à jour ou transporter intégralement chaque contexte de pipeline ; T13. |
| A10 | P0 confirmé | cdc_handshake.sv | Requête et acquittement ne traversent qu’un étage chacun. Le bus est échantillonné continuellement, sans séquence de capture destination explicitement protégée. | Mailbox à données maintenues, synchroniseurs multi-étages, capture sûre, contraintes ; T11. |
| A11 | P0 risque | cdc_handshake.sv / top_cache.sv | Reset identique distribué à plusieurs domaines, déassertion non synchronisée ; resets indépendants des toggles susceptibles de produire perte ou opération fantôme. | Contrat reset global/annulation et resets locaux synchronisés ; T04, T11, T22. |
| A12 | P0 confirmé | writeback_engine.sv:107–110 | WLAST n’est affirmé pour le dernier beat que si WREADY est haut. Le payload change avec READY pendant une attente du dernier beat. | WLAST dérivé du beat courant indépendamment de READY ; T16. |
| A13 | P0 risque fort | writeback_engine.sv:58–59,122–124 | Prélecture RAM pilotée par read_ptr_d et buffer dépendant du handshake : alignement adresse/donnée fragile avec RAM à lecture synchrone et stalls. | Pipeline RAM avec valid de donnée et tampon stable ; T16. |
| A14 | P0 confirmé | refill_engine.sv / miss_handler.sv | Fin de refill pilotée par RLAST seul ; pas de contrôle du nombre de beats, pas de traitement RRESP, RID ignoré. | Compter, contrôler LAST/ID/statut et ne valider la ligne qu’au succès ; T15, T17. |
| A15 | P0 confirmé | writeback_engine.sv / miss_handler.sv | BRESP ignoré ; la fin est signalée même sur erreur DDR. Le contrôleur peut effacer dirty puis écraser la seule copie correcte. | Conserver la victime sale sur erreur ; réponse d’erreur de bout en bout ; T16–T17, T14. |
| A16 | P0 confirmé | cache_pkg.sv / cache_controller.sv / top_cache.sv | La réponse CDC ne porte qu’un type REFILL/WRITEBACK et ce type est inutilisé côté contrôleur. Aucun statut d’erreur vers le processeur. | Type de réponse explicite avec opération/statut ; T03, T18, T22. |
| A17 | P1 confirmé | refill_engine.sv:35–37 ; writeback_engine.sv:48–50 | AxSIZE = 4 et strobe refill de 16 bits codés en dur ; les moteurs utilisent directement les commandes entrantes sans les capturer eux-mêmes. | Dériver largeurs ; définir acceptation vs achèvement ; contexte capturé dans un propriétaire unique ; T03, T15–T17. |
| A18 | P1 confirmé | cache_pkg.sv:20 | MEM_CACHE_SIZE utilise CPU_ADDR_W au lieu de CPU_DATA_W : erreur masquée par leur égalité actuelle. | Calculs en octets, assertions de géométrie ; T03. |
| A19 | P1 confirmé | cache_pkg.sv / plru.sv / concaténations | NB_LINE=1 produit NB_TAG=0 ; configurations non puissances de deux, divisions non entières, tranches nulles et burst trop long non rejetés. | Définir configurations supportées ; cas unitaire ou refus explicite ; T03, T26. |
| A20 | P1 confirmé | src/true_dual_port_ram.sv / top_cache.sv | Déclaration vide attendue pour l’IP, mais aucune sélection RTL/IP ni adaptation de contrat commune. | Wrapper RAM et manifests distincts ; T08–T10. |
| A21 | P0 confirmé | vivado/ips.tcl | IP RAM définie avec profondeur A=128 × 128 bits, soit 2 Kio ; géométrie du package = 8 Kio, donc A=512 × 128 et B=2048 × 32. | Génération depuis configuration commune, contrôle automatique ; T10. |
| A22 | P1 risque | bl_mem.sv | Tableau d’octets écrit depuis deux processus et horloges ; attribut ram_style seul insuffisant pour démontrer l’inférence BRAM. Collisions et valeur initiale non contractuelles. | Synthèse du candidat RTL, template ou bancs adaptés si nécessaire ; T09. |
| A23 | P0 confirmé | top_cache.sv:253–254 et resets | init_calib_complete et mmcm_locked sont inutilisés par le contrôle ; pas de politique explicite de démarrage/perte du MIG, reset logique différent du reset AXI MIG. | Séquencement et synchronisation de l’état prêt ; T22. |
| A24 | P0 confirmé | test/conftest.py:25–27 | Une unique compilation bl_mem est utilisée pour les tests qui demandent d’autres tops. La suite ne valide pas chaque DUT comme attendu. | Une construction par top/configuration, répertoires isolés ; T05. |
| A25 | P0 confirmé | test/test_bl_mem.py:31,75–85,93 | Affectation inachevée, MEM_SIZE float utilisé pour une liste, fautes BitArray/range, appel avec dictionnaire alors que la fonction attend des Block, avance d’horloge absente entre écritures de la boucle interne. | Réécrire le test autour d’un modèle par octet ; T08–T09. |
| A26 | P0 confirmé | test/drivers/channel_drivers.py:assert_data_stable | Assertion attend VALID=0 pendant une attente au lieu de VALID=1 ; boucle pouvant ne pas suspendre si READY est déjà haut. | Corriger moniteur et ordonnancement, tester le vérificateur lui-même ; T06. |
| A27 | P1 confirmé | channel_drivers.py / driver.py | Capacité push attend une seule fois, capture proche des fronts sans phase de lecture explicite, tâche moniteur non suivie dans triggers, fin/reset fragiles. | Contrat de scheduling, backpressure et arrêt des tâches ; T06. |
| A28 | P0 confirmé | tests refill/writeback/plru/hit_detection/transaction | PLRU sans oracle ; contrôle hit surtout stimulé ; transaction référence hit_addr_o inexistant au lieu de hit_addr_i ; tests moteurs vérifient moins de LEN+1 éléments et utilisent des modèles RAM impropres à garantir la vraie latence. | Tests dirigés avec oracle indépendant, assertions et watchdog ; T12–T17. |
| A29 | P1 confirmé | test/test_cache_controller.py | Vérification des données masquées par WSTRB : les octets censés rester inchangés ne sont pas contrôlés ; tailles de refill codées en dur ; jitter maître nul. | Comparer tout le mot, initialiser un fond non nul, randomiser indépendamment les canaux ; T18. |
| A30 | P1 confirmé | test/models/axi_dram_model.py | Modèle inachevé : attribut nu self.ar_burst, reset non défini, ports incohérents, absence de strobes ; inutilisable comme référence fiable. | Remplacer ou terminer, avec tests dédiés ; T07. |
| A31 | P1 confirmé | theoretical_dram_model.py | Adresse key multipliée par largeur, valeurs non initialisées tirées à nouveau à chaque lecture, destruction des listes transmises à set. Risque d’unités ambiguës et d’oracle instable. | API adressée en octets et initialisation déterministe persistante ; T07. |
| A32 | P1 confirmé | generated_config.py / tree.json / gen_tree.sh | Métadonnées générées consommées depuis plusieurs chemins ; modifications Python de TAG_SIZE ne reparamètrent pas le RTL. Pas de contrôle de fraîcheur automatique. | Générer par configuration de build ou retirer cette dépendance des tests critiques ; T05–T07. |
| A33 | P1 confirmé | src/save_controller.sv / src/cache.f | Ancien fichier définit aussi cache_controller ; cache.f ne liste que cache_pkg. Compilation par glob susceptible de doublon et manifeste incomplet. | Manifests explicites ; retirer l’archive des sources actives ; T05. |
| A34 | P0 confirmé | uart_src/uart_to_cache.sv | Connexion .led à un port absent de top_cache ; cycle_ct implicite/non piloté. | Corriger le top carte et lint strict ; T28. |
| A35 | P0 confirmé | uart_src/uart_to_axi.sv / data_to_axi.sv | led implicite non exposé ; pont sans canaux BRESP/BVALID et RRESP. Il répond OKAY à la fin du transfert W sans attendre la réponse d’écriture du cache. | Pont AXI complet pour l’usage retenu et propagation des erreurs UART ; T28. |
| A36 | P0 confirmé | uart_src/fifo.sv | Pointeurs sans bit de tour, compteur calculé par différence : après DEPTH écritures, plein devient vide ; wrap non puissance de deux non traité. | Compteur d’occupation ou pointeurs étendus ; T29. |
| A37 | P1 confirmé / risque | r_buffer.sv / t_buffer.sv / uart_tx.sv | RX assemble avec tranche figée de 8 bits ; TX/buffer commencent à traiter avant handshake d’entrée, protocole interne inhabituel et risque de duplication. | Réception uniquement sur valid&&ready, stockage jusqu’à émission complète ; T29. |
| A38 | P1 risque | uart_rx.sv | RX est un flux sans backpressure physique ; attente d’un consommateur peut perdre la trame suivante. Reset du synchroniseur à 0 et contrôle framing à caractériser. | FIFO/limite documentée et tests continus, framing/overrun ; T29. |
| A39 | P1 confirmé | vivado/*.tcl / board.xdc / .xpr | Chemins absolus locaux, désactivation de contraintes MIG à justifier, horloge carte commentée dans board.xdc, sources/IP externes à reconstruire. | Build batch propre et rapports check_timing/CDC/DRC ; T30. |
| A40 | P1 confirmé | lint/verilator_waiver.vlt | Exemptions larges sur IP et signaux fonctionnels d’erreur/reset/calibration ; -Wno-MULTIDRIVEN global dans les tests. | Séparer les stubs, limiter et justifier les exemptions ; T05, T30. |
| A41 | P1 spécification manquante | ensemble | Reset destructif, erreurs DDR, flush/invalidate, cohérence avec autres maîtres et limites de performance non définis. | Décisions explicites avant fermeture fonctionnelle ; T01–T04, T19. |

Les défauts AXI s’appuient sur la règle VALID indépendante de READY et stabilité jusqu’au handshake : [spécification Arm](https://documentation-service.arm.com/static/68b03beb01ae952d9559f9eb). Les contrôles de réponse et de frontière 4 Kio sont également décrits par [AMD PG101](https://docs.amd.com/r/en-US/pg101-axi-protocol-checker/AXI-Protocol-Checks-and-Descriptions). La déassertion synchronisée du reset est documentée par [AMD XPM_CDC_ASYNC_RST](https://docs.amd.com/r/en-US/pg382-xpm-cdc-generator/XPM_CDC_ASYNC_RST).

### Architecture de référence proposée

Conserver un cache bloquant pour cette version : une seule opération de cache exécutée à la fois, sans MSHR multiples ni opérations spéculatives. Le frontend peut tamponner les canaux AW et W séparément ; cela ne nécessite pas plusieurs miss simultanés. Les réponses restent stables jusqu’à acceptation.

Séparer un cœur cache simulable, exposant un maître AXI mémoire, du top physique qui ajoute MIG et horloges. Ne pas simuler la DDR3 à chaque test fonctionnel : utiliser un esclave AXI fiable, puis une campagne distincte avec les modèles vendor.

Choix RAM : paramètre d’élaboration USE_VENDOR_RAM, propagé depuis le top et les scripts. Un seul wrapper cache_ram expose les deux ports et normalise leur ordre : CPU 32 bits, mémoire 128 bits. Le choix est statique, pas un registre modifiable à chaud. L’IP doit porter un nom distinct du wrapper et les stubs ne doivent jamais être compilés avec sa définition réelle.

Contrat mémoire commun : même capacité, même découpage des octets, mêmes enables/strobes, lecture synchrone et latence visible identique, sortie conservée si port désactivé. Le comportement READ_FIRST local doit être vérifié pour la configuration choisie ; les collisions entre ports sur des octets communs ne doivent pas être utilisées comme mécanisme de synchronisation. Leur comportement physique doit être confirmé dans UG473/PG058 pour Artix-7. Le contrôle évite ces collisions ou ignore explicitement les lectures inexploitables pendant un transfert. La RAM n’est pas remise à zéro : seules les métadonnées sont invalidées.

Pour la référence 8 Kio : CPU = 2048 mots × 32 bits ; mémoire = 512 mots × 128 bits ; ligne = 256 mots CPU = 64 beats mémoire ; AxLEN = 63 ; AxSIZE = 4. Les paramètres admis doivent garantir un nombre entier de beats, la limite AXI de 256 beats et l’absence de franchissement de frontière 4 Kio, ou prévoir explicitement le découpage en plusieurs rafales. Pour cette livraison, privilégier une restriction de géométrie vérifiée à l’élaboration.

## Phases & Tasks

Efforts : 1 = très petit, 2 = petit, 3 = moyen, 5 = important. Les points servent à comparer les lots, pas à annoncer une durée. ★ indique la chaîne critique prévisionnelle. Les corrections et leurs tests appartiennent au même lot ; aucun module n’attend la fin du projet pour être testé.

### Phase 1: contrats et configuration

**Goal:** fixer le comportement vérifiable avant modification des FSM.
**Estimated effort:** 12 points.
**Milestone deliverable:** spécification du cache et des interfaces, tableau des configurations autorisées et plan de reset relus et cohérents.

| # | Task | Effort | Dependencies | Critical Path? |
|---|---|---|---|---|
| T01 | Définir AXI CPU, arbitrage lecture/écriture, nombre d’opérations en vol, ordre et progrès attendu. Retenir blocage interne et canaux AW/W indépendants. | 3 | Aucune | ★ Oui |
| T02 | Définir carte mémoire, alignement, endianness, masques, absence d’effet de bord sur erreur et sémantique de WSTRB=0. | 2 | T01 | Non |
| T03 | Corriger et centraliser géométrie/types dans cache_pkg ; réponse avec statut ; dérivation des tailles et assertions statiques ; énumérer les configurations supportées. | 3 | T01, T02 | ★ Oui |
| T04 | Définir démarrage/calibration, reset global et local, erreurs DDR, arrêt d’horloge, flush et éventuelle cohérence externe ; choisir les états de repli. | 4 | T01, T02, T03 | Non |

T04 est dimensionné 4 points, entre lot moyen et important. Il faut notamment décider si une panne de transport AXI conduit à un état fatal jusqu’au reset, plutôt que prétendre récupérer en abandonnant une rafale non terminée. Un watchdog de simulation ne constitue pas un mécanisme matériel de récupération.

### Phase 2: environnement de vérification fiable

**Goal:** rendre chaque défaut reproductible et empêcher les faux succès.
**Estimated effort:** 13 points.
**Milestone deliverable:** commande unique de collecte/build/test par module ; test de chaque moniteur avec faute volontaire ; oracle mémoire validé indépendamment du RTL.

| # | Task | Effort | Dependencies | Critical Path? |
|---|---|---|---|---|
| T05 | Réparer conftest et manifests : build par top/config, répertoires isolés, versions Python/Verilator/Cocotb figées, parsing Python, lint, CI initiale et génération fraîche des métadonnées. | 3 | T03 | ★ Oui |
| T06 | Corriger pilotes/moniteurs : phases de simulation, VALID stable, payload complet incluant strobes/LAST/statut, capacité, reset, arrêt et propagation des échecs des tâches. | 5 | T01, T05 | ★ Oui |
| T07 | Construire modèle mémoire par octet persistant et BFM AXI mémoire avec AW/W indépendants, LEN/SIZE/LAST, délais, erreurs, scoreboard et timeouts contextualisés. Tester aussi parser/wrapper Python si conservés. | 5 | T02, T03, T06 | ★ Oui |

Les tests négatifs des moniteurs doivent détecter au minimum : VALID retiré avant handshake, payload modifié sous stall, WLAST instable, réponse prématurée, donnée perdue/dupliquée. Chaque seed est journalisée et rejouable. Ne pas utiliser un modèle qui attend systématiquement READY avant VALID pour valider le DUT.

### Phase 3: RAM et CDC

**Goal:** disposer de deux stockages équivalents et de transferts d’horloge sûrs.
**Estimated effort:** 18 points.
**Milestone deliverable:** régression RAM passée sur RTL et modèle IP ; rapport de synthèse RAM ; mailbox validée en simulation et structure CDC inspectée.

| # | Task | Effort | Dependencies | Critical Path? |
|---|---|---|---|---|
| T08 | Définir cache_ram et son contrat ; créer tests communs adressés en octets avec latence et masque connus. | 3 | T03, T05, T07 | ★ Oui |
| T09 | Finaliser bl_mem ou une organisation RTL inférable ; synthèse isolée Artix-7 et correction du template selon résultat ; tester toute la capacité et les deux sens. | 5 | T08 | ★ Oui |
| T10 | Configurer IP RAM 8 Kio, nom distinct et sélection USE_VENDOR_RAM ; simulation vendor et comparaison cycle à cycle sur les opérations définies ; vérifier capacité/latence dans les rapports. | 3 | T08, T09 | ★ Oui |
| T11 | Refaire cdc_handshake : synchroniseurs requête/ack, maintien du payload, capture destination, resets, assertions, attributs ASYNC_REG et contraintes appropriées. | 5 | T03, T04, T06 | Non |
| T11b | Vérifier absence de conflit de propriété des lignes entre ports CPU/DDR et définir enables RAM utilisables ; tests d’accès concurrents légaux et détection des accès interdits. | 2 | T08, T11 | Non |

T09 et T11 sont indépendants après leurs prérequis. T10 peut préparer ses scripts pendant T09, mais la comparaison finale attend les deux implémentations. L’inférence BRAM est un critère de réussite du backend RTL, pas une supposition fondée sur ram_style. Si le tableau d’octets ne convient pas, évaluer des bancs 32 bits ou un template asymétrique supporté ; documenter toute restriction de ratio.

### Phase 4: chemins fonctionnels du cache

**Goal:** corriger protocole, métadonnées et transferts, avec leurs tests unitaires.
**Estimated effort:** 29 points.
**Milestone deliverable:** tous les modules du cœur passent leurs tests dirigés/aléatoires ; contrôleur testé avec vraie latence RAM et gestion d’erreur ; aucune perte de données lors d’éviction.

| # | Task | Effort | Dependencies | Critical Path? |
|---|---|---|---|---|
| T12 | Refaire transaction : capture AW/W indépendante, arbitrage, requête cache, lecture RAM synchrone, réponses enregistrées, erreurs d’adresse sans effet de bord. | 5 | T01–T03, T06–T08 | Non |
| T13 | Corriger plru, reset et contexte ; préférer mise à jour simple si elle suffit au timing ; oracle indépendant pour chaque accès accepté. | 3 | T03, T06 | Non |
| T14 | Refaire le contexte de miss de hit_detection : victime figée, dirty au commit, notifications PLRU par accès, validation de ligne au succès et préservation sur erreur. | 5 | T04, T07, T12, T13 | Non |
| T15 | Finaliser refill_engine : contexte stable, comptage beats, LAST, erreurs/ID, écritures RAM limitées à la destination ; fin explicite avec statut. | 3 | T03, T04, T07, T08 | Non |
| T16 | Finaliser writeback_engine : prélecture RAM, buffer et valid, compteur, WLAST stable, réponse B et conservation du statut ; test avec RAM synchrone. | 5 | T04, T07, T09, T10 | ★ Oui |
| T17 | Finaliser miss_handler : acceptation et achèvement séparés, exclusivité moteurs, mux RAM, une réponse par commande et contexte stable pendant les stalls. | 3 | T15, T16 | ★ Oui |
| T18 | Intégrer cache_controller : raccorder statut et événements de commit, arbitrage des ressources et tests scoreboards complets. | 3 | T12, T14, T17 | ★ Oui |
| T19 | Appliquer le choix maintenance de T04 : soit flush/invalidate vérifiés, soit contrat explicite de mémoire exclusivement détenue et reset destructif. | 2 | T04, T18 | Non |

### Phase 5: intégration du cœur et fermeture de vérification

**Goal:** démontrer le comportement complet sous deux horloges et fermer les scénarios d’erreur.
**Estimated effort:** 21 points.
**Milestone deliverable:** cœur complet validé avec les deux RAM, matrice de couverture remplie, régressions reproductibles et propriétés essentielles vérifiées.

| # | Task | Effort | Dependencies | Critical Path? |
|---|---|---|---|---|
| T20 | Extraire/assembler le cœur à maître AXI externe ; manifests simulation/IP sans MIG physique ; propager sélection RAM et paramètres. | 2 | T10, T11, T11b, T18 | ★ Oui |
| T21 | Installer scoreboard global CPU/mémoire : vérifier données CPU, RAM interne observable si utile, transferts DDR, métadonnées et conservation des lignes sales. | 3 | T07, T20 | ★ Oui |
| T22 | Intégrer reset/calibration/MIG dans top_cache : synchronisations locales, prêt par domaine, absence de trafic avant disponibilité, traitement des pertes de disponibilité. | 3 | T04, T11, T20 | Non |
| T23 | Régression fonctionnelle dirigée : hits, miss, remplissage, toutes victimes, évictions propres/sales, strobes, adresses limites et maintenance. | 3 | T19, T21 | Non |
| T24 | Régression temporelle et erreurs : stalls indépendants, horloges non harmoniques, erreurs R/B, resets à chaque état, absence de duplication et réponse unique. | 5 | T21, T22 | ★ Oui |
| T25 | Assertions et preuves ciblées : stabilité, bornes, unicité tags, invalidation, séquences miss, conservation dirty, contrôle CDC/PLRU ; couverture et hypothèses explicites. | 3 | T13–T18, T20 | Non |
| T26 | Matrice de paramètres, couverture des états/transitions/croisements ; campagnes multi-seeds et tests de fautes pour vérifier les checkers. | 2 | T23–T25 | ★ Oui |

### Phase 6: FPGA, démonstrateur et livraison

**Goal:** construire et valider le système utilisable sur carte.
**Estimated effort:** 18 points.
**Milestone deliverable:** bitstream reproductible, rapports de fermeture, campagne carte et documentation d’utilisation ; deux backends RAM construits et comparés.

| # | Task | Effort | Dependencies | Critical Path? |
|---|---|---|---|---|
| T27 | Nettoyer sources : isoler save_controller et tops alternatifs, déclarations IP par fileset, default_nettype none avec frontières vendor, supprimer signaux morts après audit. | 2 | T20 | Non |
| T28 | Corriger uart_to_cache, uart_to_axi et data_to_axi : ports, compteur de cycles, réponses AXI et erreurs UART ; tests de commandes et ordre. | 3 | T18, T22 | Non |
| T29 | Finaliser UART RX/TX, r_buffer, t_buffer et fifo s’ils restent dans le chemin livré ; tests framing, flux continu, stalls, wrap, plein/vide et reset. | 3 | T06, T28 | Non |
| T30 | Build Vivado batch propre : IP régénérées, chemins relatifs, horloges/reset/XDC, synthèse deux RAM, timing, CDC, DRC et ressources ; examiner chaque exemption. | 5 | T22, T26–T29 | ★ Oui |
| T31 | Campagne carte : calibration, motifs mémoire, évictions, erreurs accessibles, reset, latences hit/miss/writeback et observation ILA si nécessaire. | 3 | T30 | ★ Oui |
| T32 | Finaliser README/spec/guide de test, versions, commandes, paramètres, limites connues et archive des rapports ; critère de livraison signé. | 2 | T26, T30, T31 | ★ Oui |

### Validation détaillée par module

Les matrices ci-dessous détaillent les critères des tâches, sans ajouter une deuxième liste de travaux. Chaque test a un timeout, un résultat attendu et une seed lorsqu’il est aléatoire.

#### cache_pkg.sv — T03, T26

- Vérifier les valeurs de référence : capacité, lignes, offsets, tags, nombre de beats et correspondance des deux adressages RAM.
- Corriger CPU_ADDR_W dans le calcul de capacité mémoire ; adopter noms indiquant bits, octets, mots ou LEN.
- Dériver AxSIZE et les strobes de MEM_DATA_W ; distinguer nombre de beats et AxLEN=nombre−1.
- Vérifier statiquement : puissances de deux requises, lignes entières, largeur CPU/mémoire compatible, adresses suffisantes, capacité positive, burst admissible et absence de tranches nulles.
- Tester au moins 2/4/8/16 voies, tailles de lignes/caches petites et référence ; 1 voie seulement si explicitement supportée. Tester le refus clair des configurations invalides.
- Une modification de configuration recompile réellement le RTL et régénère les métadonnées des tests.

#### transaction.sv — T12

- AW avant W, W avant AW, AW/W simultanés et écart de plusieurs cycles ; aucun B avant réception complète.
- AR/AW simultanés, demandes continues, réponse R bloquée et réponse B bloquée ; ordre et absence de famine selon le contrat T01.
- Consommateur R qui ne monte RREADY qu’après RVALID ; payload/valid stables pendant des stalls longs, même lorsque les entrées changent après leur acceptation.
- RAM synchrone avec motif différent par voie/adresse ; premier mot après refill, changement de voie, lecture après écriture et frontières de ligne.
- Tous les masques CPU, dont zéro ; les octets non sélectionnés restent inchangés.
- Adresses 0, dernier mot légal, première adresse hors plage, chaque désalignement et adresses hautes ayant les mêmes bits bas qu’une adresse valide ; SLVERR sans modification de RAM, tag, dirty ou DDR.
- Une seule réponse par transaction ; aucune modification après réponse finale ; reset à chaque état conformément à T04.

#### plru.sv — T13

- Initialisation déterministe de READY, VALID et arbre ; pas de X sur contrôle après reset dans un simulateur 4 états.
- Oracle tree-PLRU indépendant, pas un oracle vrai LRU : les politiques diffèrent.
- Vérifier séquences connues, répétition d’une voie, toutes les voies et accès successifs acceptés au débit maximal.
- Couvrir les 128 états d’arbre pour 8 voies si atteignables par les séquences ; sinon justifier les états exclus et couvrir les transitions atteignables.
- Contexte correctement aligné à travers le pipeline ; sortie valide et victime stable pendant la réservation par le contrôleur.

#### hit_detection.sv — T14

- Reset invalide toutes les lignes ; hit uniquement pour tag valide ; aucun tag valide dupliqué.
- Première allocation, remplissage de chaque emplacement, cache plein, victime propre et sale ; vérifier adresses mémoire et RAM émises.
- Figer la victime même si le PLRU change pendant l’attente ; stabilité des requêtes sous backpressure.
- Une notification PLRU par accès achevé, y compris plusieurs hits consécutifs sans miss ; aucune notification répétée pendant un stall.
- dirty ne monte qu’au commit d’une écriture effective ; WSTRB=0 et accès rejeté ne le modifient pas.
- Après writeback réussi puis refill : ordre exact WB→RF ; après erreur WB : pas de refill destructif, dirty et données conservés.
- Après erreur refill : pas de ligne partiellement chargée valide. Définir le traitement de la victime propre déjà écrasée : invalidation avant refill ou restauration explicitement prouvée.
- Reset pendant chaque phase et accès suivant après erreur : pas de faux hit ni dépendance au tag incomplet.

#### cache_controller.sv — T18

- Combinaison transaction/tags/PLRU testée avec le stockage synchrone réel, pas uniquement une RAM dictionnaire à lecture immédiate.
- Comparer chaque mot CPU intégralement au modèle par octet, et les requêtes DDR à l’état attendu.
- Réécriture partielle répétée, lecture après modification et après éviction/rechargement ; latences de réponse variables.
- Interdire double réservation d’une voie, opération RAM sur adresse invalide et commit double.
- Supprimer ou isoler la version historique et les blocs commentés après stabilisation.

#### refill_engine.sv — T15

- Tester LEN=0, LEN=1, LEN=63 et maximum supporté, avec base RAM nulle/non nulle et dernière ligne physique.
- ARREADY retardé ; RVALID avec trous, réponses consécutives, dernier beat et stabilité des commandes.
- Exactement LEN+1 écritures, uniquement sur handshake R ; aucune écriture avant AR accepté ou après fin.
- Compter indépendamment de RLAST ; faute LAST prématuré, absent ou tardif : diagnostic et repli déterministes, pas de corruption d’une autre ligne.
- RRESP erreur au premier, milieu et dernier beat ; statut transmis et ligne invalidée. RID différent : violation détectée selon contrat.
- Erreur de protocole et backpressure légal sont des cas distincts ; ne pas promettre une récupération de transport non définie.

#### writeback_engine.sv — T16

- Utiliser une vraie RAM READ_FIRST synchrone et des données non triviales différentes à chaque beat ; contrôler premier et dernier beat.
- AWREADY, WREADY et BVALID retardés indépendamment ; stall sur premier, milieu et dernier beat.
- WDATA/WSTRB/WLAST/WVALID maintenus pendant tout stall ; WLAST haut pour le dernier beat même si WREADY=0.
- Nombre exact de beats, pas de duplication/perte au redémarrage après stall, bonne adresse pour chaque ligne et limites de RAM.
- B accepté après dernier beat ; un seul statut de fin ; BRESP erreur propagé sans effacer la seule copie correcte.
- LEN=0/1/63/maximum supporté, commandes consécutives et reset à chaque état.

#### miss_handler.sv — T17

- Distinguer commande acceptée et opération finie ; supprimer l’ambiguïté de addr_ready comme signal de fin interne, par renommage ou contrat précis.
- Commande entrante différente après acceptation : contexte courant inchangé.
- Séquences RF/RF, WB/WB, WB/RF, RF/WB ; réponse retenue tant que le destinataire n’est pas prêt.
- Un seul moteur actif, mux RAM correct et pas de WE hors refill ; une réponse par commande acceptée avec bon statut/opération.
- Paramètres AXI fixes ID/cache/prot/burst conformes au choix documenté ; vérifier les IDs de retour utiles.

#### cdc_handshake.sv et resets — T11, T22

- Payload stable à la source depuis capture jusqu’à acquittement ; destination présente une valeur complète, maintenue jusqu’à consommation.
- Synchroniseurs multi-étages dans les deux sens, avec attributs et reconnaissance dans report_cdc ; le bus utilise un protocole bundled-data justifié, pas une synchronisation indépendante de chaque bit.
- Rapports de périodes 1:1 avec phases différentes, source rapide, destination rapide, rapports non entiers ; backpressure destination et rafales source.
- Comparer listes de commandes/réponses : ordre, égalité, aucune perte ni duplication, y compris au débit maximal de la mailbox.
- Reset global en attente de requête/ack ; reset local uniquement si T04 le supporte. Sinon vérifier son interdiction et le reset commun requis.
- Arrêt/reprise d’une horloge sans reset pour sécurité et maintien des données ; progrès seulement lorsque les deux horloges fonctionnent.
- Simulation numérique pour le protocole ; analyse CDC/RDC et timing pour les risques physiques. Une simulation aléatoire seule ne démontre pas l’absence de métastabilité.

#### cache_ram, bl_mem, true_dual_port_ram/IP — T08–T11b

- Test commun sélectionné par backend, pas deux suites divergentes.
- Initialiser explicitement le contenu utilisé ou tenir un masque d’octets connus ; aucune hypothèse de zéro au démarrage.
- Marches d’adresses et motifs 00/FF/AA/55, walking bit, adresse encodée, données aléatoires ; toutes adresses et frontières physiques.
- CPU→mémoire et mémoire→CPU : chaque groupe de quatre mots CPU correspond au même beat mémoire et bon ordre des octets.
- Masques : tous les 16 masques CPU ; chaque octet mémoire isolé, zéro, plein, motifs et masques aléatoires, voire les 65536 masques mémoire sur une campagne dédiée.
- Lecture seule, écriture seule, enable désactivé, READ_FIRST local, maintien de sortie et latence à un cycle ou latence explicitement normalisée.
- Horloges indépendantes, phases balayées, accès simultanés à régions disjointes ; assertion des collisions interdites plutôt qu’un résultat inventé pour deux écritures concurrentes au même octet.
- Vérifier les lectures parasites provoquées par enables à 1 pendant refill/writeback ; les inhiber lorsqu’elles exposent une collision interdite par la configuration vendor.
- Équivalence RTL/modèle IP sur le domaine défini ; synthèse isolée des deux : BRAM/LUT/FF, latence, mode, profondeur et absence de mémoire distribuée inattendue.
- Tester réellement la branche IP avec XSim/modèle vendor si Verilator ne supporte pas ces modèles ; ce test fait partie de la livraison.

#### top_cache.sv, adam_mig.sv, Vivado — T20, T22, T30

- adam_mig.sv est une déclaration d’IP attendue : conserver pour lint contrôlé, exclure lorsque l’IP réelle est compilée.
- Extraire le cœur pour tests AXI, conserver le top physique pour DDR3, IP et séquencement.
- Utiliser ui_clk_sync_rst et la disponibilité MIG selon le contrat ; synchroniser calibration/lock vers CPU ; vérifier polarité réelle. mig.prj indique actuellement reset actif bas : ne pas inverser au hasard.
- Aucune requête mémoire avant calibration ; définir si le frontend peut tamponner une requête puis attendre, ou reste fermé.
- Vérifier les bits d’adresse supprimés avant MIG : ils doivent être rejetés plus haut, jamais créer un alias silencieux.
- Générer IP et projet depuis un checkout propre, sans dépendre du répertoire cache_multiple_lines.gen local.
- Examiner chaque XDC MIG activée/désactivée, les clocks générées, entrées/sorties, faux chemins et contraintes de mailbox. Ne pas masquer tout un bus CDC sans justification de protocole et de délai.
- Rapports synthèse/implémentation : aucune black box involontaire, aucun latch imprévu, aucune horloge non contrainte, violations timing et DRC bloquantes résolues, exemptions CDC documentées.

#### UART et démonstrateur — T28–T29

- uart_to_cache : ports cohérents, LED au niveau approprié, cycle_ct défini, reset/lock corrects, fréquence réelle de clk_cpu utilisée pour le baudrate.
- data_to_axi : attendre BVALID/BREADY et contrôler BRESP avant write_done ; conserver les paramètres capturés, contrôler RRESP et maintenir les payloads sous attente.
- uart_to_axi : parsing déterministe sur handshake, commande/adresse/donnée mémorisées, statut OKAY uniquement après succès, commandes inconnues/tronquées traitées explicitement.
- r_buffer/t_buffer : nombre de fragments dérivé des largeurs, ordre des octets, données stables jusqu’au handshake, pas d’envoi double lors d’un READY tardif.
- uart_rx/uart_tx : trame 8N1 vérifiée par récepteur/transmetteur indépendant, bauds extrêmes supportés, léger décalage de baud, faux start, framing, break, trames consécutives et reset en milieu de trame. Le stop/idle de TX doit être mesuré, pas validé par un loopback qui partage le même défaut.
- fifo : vide/plein exacts, DEPTH écritures, DEPTH lectures, wrap multiples, lecture/écriture simultanées aux limites, overflow/underflow, profondeur unitaire ou refus explicite et profondeurs non puissances de deux selon support.
- Conserver uniquement le top livré dans le build principal ; top_uart et les alternatives restent dans des manifests séparés ou sont archivés avec leur statut.

#### Outils Python et tests — T05–T07

- Tester parser Verible sur paramètres dépendants, enums, structs imbriquées, membres signés, largeurs inconnues et ports scalaires ; erreurs explicites pour les constructions non supportées.
- Tester DutWrapper sur offsets packed, lectures/écritures de champs, conservation des autres champs, commits multiples, signal brut et mécanisme de flush avant front. Documenter l’API réellement requise : un await cocotb ordinaire ne doit pas être supposé faire un commit si ce n’est pas garanti.
- Éviter les références relatives ../tree.json dépendantes du répertoire d’exécution ; empreinte des sources/configurations dans les artefacts.
- Ne jamais corriger uniquement une constante Python en supposant modifier le matériel.
- Ajouter tests des pilotes et du modèle contre un composant de référence simple ; vérifier les nombres de transferts observés aux fronts.
- Modèle mémoire à adresses en octets explicites ; données non initialisées persistantes ou indéfinies suivies comme telles ; aucune mutation surprise des listes de l’appelant.

### Campagnes de validation et critères de sortie

| Niveau | Campagne minimale | Critère de réussite |
|---|---|---|
| Syntaxe/build | Tous les Python analysés, tests collectés ; chaque top compilé dans un répertoire neuf | Zéro erreur ; aucune réussite obtenue à partir d’un binaire obsolète |
| Lint | Cœur, RAM RTL, top carte avec stubs isolés | Aucun défaut fonctionnel caché ; exemptions précises et revues |
| Unitaire | Matrices ci-dessus et reset à chaque état | Chaque cas a un oracle ; aucun test purement visuel |
| RAM | Deux backends, toutes adresses, strobes et rapports d’horloge | Résultats et latence identiques pour les opérations définies ; BRAM démontrée |
| Intégration | Petit cache de test et cache 8 Kio, plusieurs horloges, miss forcés | Scoreboard complet sans perte, réponse unique et ordre conforme |
| Aléatoire | Base proposée : 20 seeds × 10000 opérations pour régression, puis 100 × 100000 pour fermeture | Zéro divergence/timeout ; ajuster la taille selon couverture et coût mesuré |
| Erreurs | RRESP/BRESP, LAST fautif, adresse illégale, reset et indisponibilité MIG | Comportement prévu observé ; données sales préservées ou perte contractuellement limitée au reset destructif |
| Propriétés | Stabilité AXI, unicité tag, bornes RAM, séquencement WB/RF, contrôle CDC/PLRU | Assertions toujours actives ; preuves bornées ciblées et hypothèses documentées |
| Couverture | États/transitions, voie × hit/miss × lecture/écriture × propre/sale ; stalls × premier/milieu/dernier beat ; reset × état ; backend × configuration | 100 % des cas dirigés et bins exigibles ; trous et exclusions justifiés. Aucun pourcentage brut de lignes ne remplace cela |
| Vivado | Synthèse/implémentation deux backends, timing, CDC/RDC, DRC | Pas de violation bloquante ni black box inattendue ; contraintes complètes |
| Carte | Calibration répétée, motifs, capacité, évictions, UART, reset, mesures | Rapport rejouable avec versions, bitstream, commandes et résultats |

La vivacité est conditionnelle : si le maître n’accepte jamais la réponse, si la DDR ne répond jamais ou si une horloge reste arrêtée, aucun délai fini ne peut être garanti. Les tests distinguent les timeouts du banc, les limites contractuelles et les éventuels mécanismes matériels de repli.

### Scénarios de bout en bout indispensables

1. Charger une ligne par lecture, relire tous ses mots, vérifier qu’aucun nouveau trafic DDR n’est généré.
2. Écrire une ligne absente avec un masque partiel sur fond non nul, relire tous les octets, évincer puis recharger et comparer intégralement.
3. Remplir les huit voies avec des motifs distincts, imposer des accès PLRU connus et provoquer la neuvième allocation ; contrôler la victime réelle.
4. Enchaîner évictions propres et sales sous stalls mémoire, notamment WREADY=0 au dernier beat et BVALID très retardé.
5. Lire immédiatement le premier et le dernier mot d’une ligne après refill, puis changer de voie à chaque requête.
6. Accéder à une adresse invalide partageant les bits bas d’une ligne sale ; vérifier absence de toute modification ou rafale DDR.
7. Faire échouer un writeback ; constater l’erreur CPU, la conservation de la ligne sale et l’absence de refill destructif.
8. Faire échouer un refill au milieu ; aucune lecture ultérieure ne doit voir une ligne partiellement valide.
9. Bloquer la réponse CPU et changer les entrées déjà consommées ; réponse et donnée doivent rester stables.
10. Répéter les scénarios avec horloges non harmoniques et chacun des deux backends RAM, puis tester les resets selon T04.

## Critical Path Summary

Chaîne prévisionnelle : T01 → T03 → T05 → T06 → T07 → T08 → T09 → T10 → T16 → T17 → T18 → T20 → T21 → T24 → T26 → T30 → T31 → T32.

La RAM et sa latence conditionnent directement le writeback, puis la conservation des données dans le système complet. Une divergence entre les backends retarde la vérification des moteurs et la fermeture FPGA. La chaîne devient définitive après les premières synthèses et tests : le travail sur transaction, hit_detection ou CDC peut la rejoindre si ces lots dépassent leur estimation. Les ★ sont donc une projection fondée sur les dépendances et efforts, pas une promesse de calendrier.

Travaux indépendants possibles après contrats : CDC, PLRU, frontend AXI, préparation IP et infrastructure de tests. Leur parallélisation relève de l’organisation de l’implémentation ; aucune délégation d’agents n’a été effectuée pour cet audit.

## Risks & Assumptions

- Hypothèse : conserver entièrement associatif, write-back/write-allocate, cache bloquant et interface CPU 32 bits pour la première livraison. Étendre les performances ensuite si les mesures l’exigent.
- Hypothèse : la référence matérielle reste Nexys Video / Artix-7 identifiée dans le .xpr ; les fréquences exactes et contraintes sont vérifiées dans T04/T30.
- Risque : RTL RAM simulable mais non inféré en BRAM. Réduction : synthèse isolée précoce et ajustement de l’organisation, avec test identique à l’IP.
- Risque : les modèles du banc reproduisent les défauts du DUT. Réduction : oracle par octet indépendant, checkers testés par fautes et modèles vendor pour la fermeture IP.
- Risque : reset détruit des données sales. Réduction : reset destructif documenté ; flush avant reset logiciel si conservation requise. Un reset d’urgence pendant une panne ne garantit pas une sauvegarde.
- Risque : erreur DDR en cours de rafale non récupérable proprement. Réduction : distinguer erreur de réponse légale et violation de protocole ; prévoir état fatal/reset global pour les cas où le transport ne peut être resynchronisé.
- Risque : autre maître DDR incohérent avec le cache. Réduction : mémoire détenue exclusivement pour cette version, ou protocole de flush/invalidate et exclusion mutuelle explicitement ajouté. La cohérence multicœur matérielle n’est pas incluse implicitement.
- Risque : 1 Kio par ligne amplifie le coût d’un miss. Réduction : mesurer taux de hit, cycles de hit/miss propre/miss sale, débit et ressources ; modifier la géométrie après validation fonctionnelle, pas pendant sa stabilisation.
- Risque : analyse 2 états cache contrôles non initialisés. Réduction : lint et simulation 4 états ciblée avec XSim ou autre simulateur adapté.
- Risque : IP dépendantes de licences/installations et carte non accessible. Réduction : CI fonctionnelle sans IP et jalon vendor explicite ; ne pas déclarer la livraison FPGA terminée sans ses résultats.
- Limite : aucune couverture finie de simulation n’est une preuve intégrale de tous les comportements. La fermeture associe tests, assertions/propriétés ciblées, analyse CDC et timing, puis mesures réelles.

## Open Questions (if any)

Aucune question ne bloque ce plan. Avant l’implémentation, T01–T04 doivent acter trois décisions de produit : conservation des données lors d’un reset logiciel, accès DDR par d’autres maîtres, et objectifs de fréquence/débit. Les hypothèses proposées permettent d’avancer sans inventer leurs réponses.
