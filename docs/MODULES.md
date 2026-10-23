# Architecture et vérification par module

Ce document décrit l’implémentation actuelle. Le plan historique conserve les défauts initialement relevés ; ils ne décrivent plus nécessairement le code corrigé. Les tests sont lancés dans `cache_design`, avec Verilator et Cocotb, à l’exception de la comparaison avec le modèle réel de RAM Vivado, exécutée dans XSim.

## Cœur du cache

| Module | Rôle et comportement | Vérification actuelle |
|---|---|---|
| `cache_pkg` | Géométrie, commandes packed, opération REFILL/WRITEBACK et réponse avec statut AXI. Capacité mémoire calculée à partir de la largeur de données CPU. | Test d’accès natif aux structs, assertions de géométrie du cœur et compilation de tous les modules. La configuration complète testée est 8 Kio / 8 lignes / 1 Kio. |
| `plru` | Arbre dont chaque bit pointe vers le sous-arbre moins récemment utilisé. Mise à jour de tout le chemin sur chaque accès accepté ; un accès par cycle, aucun contexte de pipeline partagé. | Oracle Python indépendant, accès consécutifs, pauses et reset ; 1, 2, 4, 8 et 16 voies. |
| `reset_sync` | Assertion asynchrone, relâchement après deux fronts locaux. Utilisé séparément dans chaque domaine du cœur et pour le pont UART. | Reset sans horloge et relâchement sur exactement deux fronts. |
| `cdc_handshake` | Mailbox à une entrée. Donnée source maintenue jusqu’à acquittement, synchroniseurs requête/ack à deux étages, copie destination stable sous backpressure. L’un des resets annule la mailbox entière. | 430 transferts avec rapports d’horloge différents, ordre/conservation, attente prolongée, absence de doublon et reset d’un transfert en attente. La fermeture physique CDC/RDC reste un jalon distinct. |
| `transaction` | Tampons AW, W et AR indépendants. Un arbitre alterne les opérations éligibles. Requête de tag, attente RAM synchrone, capture du résultat puis réponse enregistrée. Erreurs d’adresse et WSTRB nul traités avant recherche du cache. | Toutes les voies et tous les masques CPU, AW/W désynchronisés, entrées modifiées après acceptation, réponses bloquées, concurrence lecture/écriture, erreurs d’adresse et erreurs de lookup. |
| `hit_detection` | Tags valid/dirty, recherche associative et réservation d’une victime. dirty est mis à jour au commit réel. Séquence writeback puis refill ; aucune réutilisation d’une ligne sale avant succès. Une ligne partiellement rechargée reste invalide. | Allocations, hits répétés et événements PLRU, victime figée malgré changement du PLRU, éviction sale, erreur WB avec conservation, erreur RF sans faux hit. |
| `cache_controller` | Assemble frontend, tags et remplacement. Transporte le statut de retour mémoire jusqu’à la réponse CPU. Fournit un enable RAM pour les seuls accès effectifs. | Modèle RAM synchrone et mémoire par octet : 20 lignes, masques et relectures, erreurs WB/RF, zéro effet de bord sur adresse illégale ou masque nul. |
| `refill_engine` | Capture une commande, émet AR, compte les beats et écrit la RAM sur handshake. Vérifie RRESP et RLAST. Une réponse trop longue est drainée sans écrire hors de la ligne. | 1/2/16/64/256 beats, dernière ligne RAM, pauses, erreurs au début/milieu/fin, LAST prématuré/tardif, reset pendant refill. Pas de progrès garanti si LAST ne revient jamais. |
| `writeback_engine` | Prélecture d’une RAM synchrone, maintien du payload W pendant une pause et WLAST indépendant de READY. Termine après le handshake B ; remonte le statut B. L’appelant maintient la commande jusqu’à fin. | Longueurs/limites, première/dernière donnée, pauses premier/milieu/dernier beat, aléatoire, resets dans les phases, erreurs BRESP. |
| `miss_handler` | Accepte puis capture une commande. Active un seul moteur et conserve une réponse typée jusqu’à acceptation. ID mémoire fixé à zéro ; un ID retour inattendu produit une erreur. | Commandes mélangées, changement des entrées après capture, RAM synchrone, réponse bloquée, RRESP/BRESP et IDs incorrects. |
| `bl_mem` | Backend RTL asymétrique. Banques d’octets indépendantes et sélection de groupe enregistrée ; lecture synchrone READ_FIRST. Index de ligne explicitement non signé. | Capacité entière dans les deux sens, tous les masques CPU, masques mémoire, enable et READ_FIRST. Synthèse Artix-7 : 16 RAMB18E1, 36 LUT logiques, aucune LUT mémoire. |
| `true_dual_port_ram` | Wrapper CPU 32 bits / mémoire 128 bits. Paramètre `USE_VENDOR_RAM` pour choisir RTL ou IP `cache_ram_ip`, sans changement de ports ni de latence visible. | Mapping et masques dans Cocotb ; comparaison des deux backends sur toute la capacité avec le modèle réel BMG dans XSim. |
| `cache_core` | Cache simulable à deux horloges : contrôleur, mailbox aller/retour, gestionnaire de miss et RAM réelle. Les ports RAM sont désactivés lorsqu’ils ne sont pas exploités. | Évictions/rechargements sur deux horloges, données intégrales, erreurs traversant les CDC et conservation après échec. |
| `top_cache` | Ajoute le MIG physique au cœur commun. Bloque le cœur tant que calibration/lock/reset MIG ne sont pas prêts. Perte de calibration : reset destructif du cœur. | Simulation avec un substitut AXI/MIG clairement identifié : démarrage bloqué, évictions et perte/reprise de calibration. L’IP DDR3 réelle est vérifiée séparément par le build FPGA ; le substitut n’est pas une simulation électrique DDR3. |
| `adam_mig` | Déclaration de l’interface de l’IP MIG, sans implémentation manuscrite. Le build réel génère le contrôleur depuis la configuration DDR3 du dépôt. | Le stub est exclu quand l’IP réelle ou le modèle de test est présent. Vérification de l’interface au niveau du top ; synthèse et fermeture physique avec le vrai MIG requises. |

L’ancien `src/save_controller.sv`, qui redéfinissait `cache_controller`, est archivé sous `docs/legacy/cache_controller_monolithic.sv.txt`. Il n’est plus une deuxième implémentation active à compiler ou à maintenir.

## Interface série et tops

| Module | Rôle et comportement | Vérification actuelle |
|---|---|---|
| `fifo` | Mémoire synchrone avec sortie combinatoire, compteur d’occupation et pointeurs avec wrap explicite. Requête d’écriture à plein ou de lecture à vide rejetée, même avec opération opposée simultanée. | Oracle deque, capacité exacte, wrap répété, plein/vide, opérations simultanées et reset ; profondeurs 1/2/3/16/256. |
| `r_buffer` | Assemble les fragments UART en mots, fragment de poids faible en premier. Maintient le mot valide jusqu’au handshake ; désactivation vide le buffer. | Ordre, pauses et stabilité, 100 mots par configuration ; 32/8, 16/4 et 8/8 bits. |
| `t_buffer` | Capture le mot uniquement sur handshake, puis émet ses fragments dans l’ordre. Maintient fragment et VALID sous backpressure. | Comparaison exacte du flux, absence d’émission avant acceptation, pauses ; mêmes trois configurations. |
| `uart_rx` | Synchronise la broche RX, valide le start à mi-bit et échantillonne les données/stop. Mailbox d’un mot, alarmes de framing et overrun. Un overrun n’écrase pas le mot en attente. | Source série indépendante, tous les octets, phase/baud légèrement différents, mot bloqué, stop fautif et overrun. |
| `uart_tx` | Trame start + données LSB-first + stop, sans parité. Capture l’entrée sur handshake et garde TX au repos haut. | Décodeur indépendant, tous les octets, modification immédiate de l’entrée après acceptation, start/stop et retour prêt. |
| `data_to_axi` | Capture les commandes read/write et gère les canaux AXI indépendants. Une écriture ne termine qu’après B ; lecture après R. Les résultats et statuts sont maintenus jusqu’à acquittement du client. | Reads/writes concurrents, délais AW/W/B, entrées empoisonnées après capture, statuts 0/2/3, sorties done maintenues et pas de duplication. |
| `uart_to_axi` | Parse les commandes série et utilise le pont AXI. Réponse OKAY après succès, ERR! sur erreur AXI. Une perte de framing déclenche ERR! puis impose un reset pour éviter des commandes désalignées. | Dialogue depuis les broches série : WRIT/READ/CMDA/TEMP/inconnue, données, erreurs R/B, faute de framing et récupération après reset. |
| `top_uart` | Démonstrateur : reçoit un burst de mots dans le FIFO puis le retransmet. | Deux bursts série complets et ordre exact des octets, avec FIFO de profondeur non puissance de deux. |
| `uart_to_cache` | Top Nexys Video : clock wizard, reset local, compteur de cycles, pont série et cache. LED0 indique le lock, LED1 mémorise une erreur RX. | Parcours série → cache → modèle MIG, 12 lignes sales avec évictions, relectures et adresses illégales. Simulation ne remplaçant pas la validation carte. |

## Interfaces de test et scripts

Les nouveaux tests utilisent de petits bancs locaux et trois auxiliaires ciblés : maître CPU AXI-Lite, mémoire AXI et lien série indépendant. Les références mémoire vérifient les mots entiers et les octets conservés, pas uniquement les bits sélectionnés par les strobes. Aucune dépendance au wrapper de structs ni au JSON Verible n’est nécessaire.

`src/cache.f` liste les sources actives du cœur depuis la racine. Les modèles `test/rtl/adam_mig_model.sv` et `clk_ref_mig_model.sv` ne doivent jamais être inclus dans une construction matérielle. Le modèle MIG de test est limité à 64 Kio et à des rafales de 128 bits ; le contrôleur réel conserve sa configuration DDR3 512 Mio.

Scripts Vivado :

- `scripts/synth_ram.tcl` vérifie l’inférence BRAM du backend RTL.
- `scripts/create_ram_ip.tcl` génère l’IP RAM de 8 Kio avec la bonne géométrie et une latence d’un cycle.
- `scripts/simulate_ram_backends.tcl` exécute l’équivalence XSim et vérifie un marqueur de succès explicite ; un retour processus nul après `$fatal` ne suffit pas.
- `scripts/build_fpga.tcl` génère RAM, horloges et MIG, puis synthétise le top carte ; l’argument `impl` demande aussi placement/routage et bitstream.

Les broches de la carte sont vérifiées dans le [Master XDC Digilent](https://github.com/Digilent/digilent-xdc/blob/master/Nexys-Video-Master.xdc). Le sens TX/RX est confirmé par le [manuel officiel](https://digilent.com/reference/_media/reference/programmable-logic/nexys-video/nexys-video_rm.pdf). Le clock wizard est l’unique entrée d’horloge physique : le MIG reçoit une horloge interne configurée « No Buffer ».

## Résultats et limites

La régression consolidée comprend 44 cas pytest réussis. Les deux backends RAM sont synthétisés, routés et testés sur la Nexys Video avec la vraie DDR3 : chacun réussit 1781 commandes UART sur 258 mots, dont 1000 opérations aléatoires. Les campagnes de reset et d'erreurs ainsi que quatre géométries du cœur sont validées en simulation.

Les chiffres, avertissements physiques résiduels et limites de couverture sont conservés dans [VERIFICATION_STATUS.md](VERIFICATION_STATUS.md). Le protocole de reproduction sur carte est décrit dans [BOARD_TEST.md](BOARD_TEST.md). La couverture formelle et la mesure précise des latences ne sont pas closes par ces résultats.
