# Passation technique — cache FPGA

État de référence : 23 octobre 2026. Ce document transmet le contexte de travail ; le RTL et les résultats archivés restent les références à vérifier avant une nouvelle modification.

Deux périmètres sont présents dans le workspace : le cache autonome à la
racine et son intégration dans le clone `adam/`. Pour reprendre le travail ADAM,
lire d’abord [ADAM_INTEGRATION_HANDOFF.md](ADAM_INTEGRATION_HANDOFF.md). Cette
intégration est maintenant simulée, routée et testée sur la Nexys Video ; les
paragraphes historiques ci-dessous sur le cache autonome restent valides dans
leur propre périmètre.

## Demande et préférences de l’utilisateur

L’objectif est de comprendre chaque module RTL, corriger les défauts, écrire des tests robustes et lisibles, puis valider les modules et les tops en suivant le plan initial. La RAM finale peut utiliser une IP Vivado ; une implémentation RTL sélectionnable est également souhaitée et désormais disponible.

- Échanges et documentation en français ; commentaires et docstrings du code en anglais.
- Bancs simples, scénarios nommés, assertions proches du comportement vérifié ; éviter les frameworks et abstractions inutiles.
- Conserver Cocotb et la configuration de simulation existante, utiliser Verilator dans Docker, conteneur `cache_design`.
- Les dépendances Docker peuvent être adaptées, mais éviter un rebuild coûteux si le conteneur actuel suffit.
- L’utilisateur a branché la Nexys Video et son UART pour les essais. Ne pas supposer que les périphériques sont encore présents lors d’une reprise.

## Lecture conseillée

1. [README](../README.md) : vue d’ensemble.
2. [Contrat](CACHE_CONTRACT.md) : comportement attendu, erreurs, reset et hypothèses.
3. [Modules](MODULES.md) : responsabilité et validation de chaque module.
4. [État de vérification](VERIFICATION_STATUS.md) et [résultats archivés](VALIDATION_RESULTS.json) : preuves et limites actuelles.
5. [Guide des tests](../test/README.md) et [guide carte](BOARD_TEST.md) : reproduction.
6. Pour ADAM : [passation dédiée](ADAM_INTEGRATION_HANDOFF.md), puis
   [`adam/docs/DRAM_INTEGRATION.md`](../adam/docs/DRAM_INTEGRATION.md) et
   [`adam/docs/BOARD_TEST.md`](../adam/docs/BOARD_TEST.md).
7. [Plan initial](PLAN_FINALISATION_CACHE.md) : audit historique et pistes restantes. Ses défauts initiaux ne décrivent pas tous l’état actuel ; les recouper avec le RTL et l’état de vérification.

Lire ensuite les sources et tests de la partie à modifier. Les documents seuls ne remplacent pas cette lecture pour comprendre complètement les contraintes temporelles.

## Architecture et décisions à préserver

Configuration par défaut : cache bloquant entièrement associatif, write-back/write-allocate, 8 Kio, huit lignes de 1 Kio. AXI-Lite CPU 32 bits, AXI DDR 128 bits, mémoire externe 512 Mio.

Parcours CPU : `transaction` mémorise indépendamment AW/W/AR et arbitre les opérations ; `hit_detection` gère tags, valid/dirty et séquence des miss ; `plru` propose la victime. `cache_controller` rassemble ces modules. `cache_core` ajoute les deux mailboxes CDC, le gestionnaire de miss et la RAM. `miss_handler` sérialise `writeback_engine` et `refill_engine`. `top_cache` ajoute le vrai MIG ; `uart_to_cache` fournit le démonstrateur série et les horloges.

- Les réponses AXI sont maintenues sous backpressure. Une lecture CPU capture la donnée après la latence RAM synchrone.
- Les commandes internes des moteurs sont maintenues jusqu’à leur terminaison, et non seulement jusqu’à une acceptation initiale. Consulter leurs interfaces avant de modifier un handshake.
- La victime est figée pendant un miss. Un writeback en erreur conserve la ligne sale ; un refill échoué ne valide pas la ligne.
- Le statut R/B traverse les CDC jusqu’à la réponse CPU. Les adresses CPU désalignées ou hors plage donnent SLVERR sans effet de bord ; WSTRB nul ne modifie pas la ligne.
- Le reset annule les transactions et détruit les données sales. Pas de flush implicite ni de cohérence avec un autre maître DDR.
- Les mailboxes sont à une entrée : payload conservé, synchronisation requête/acquittement, annulation par reset des deux côtés. Les contraintes physiques associées sont dans `constraints/cache_cdc.xdc`.
- `reset_sync` expose directement la sortie du dernier registre de synchronisation. Une ancienne combinaison supplémentaire avec le reset brut produisait de nombreux chemins CDC critiques.
- Les registres commandant les ports RAM utilisent un reset synchrone. Revenir à un reset asynchrone peut réintroduire les avertissements Vivado REQP-1839/1840. Les handshakes externes sont annulés au reset ; les modèles de test doivent suspendre leurs contrôles de transaction durant celui-ci.

## RAM : pièges déjà rencontrés

`true_dual_port_ram` sélectionne `cache_ram_ip` avec `USE_VENDOR_RAM=1`, ou `bl_mem` avec `0`. Même mapping et latence d’un cycle, masques par octet, READ_FIRST. Le backend RTL utilise des banques d’octets pour permettre l’inférence BRAM avec deux largeurs de ports.

Une ancienne description fonctionnait dans Verilator mais ne s’inférait pas en BRAM. Un index signé dans la version suivante fonctionnait en simulation à deux états mais échouait dans XSim. Le signal de rangée `row_a` est maintenant explicitement non signé. Conserver les vérifications de synthèse et d’équivalence XSim lors des changements RAM.

Les conflits simultanés entre ports sur les mêmes octets ne sont pas une sémantique garantie. Le fonctionnement du cache doit les exclure pour les données exploitées.

## Environnement effectivement utilisé

Workspace hôte : `/home/johann/cache`, monté dans le conteneur sous `/phinaow`.

```bash
scripts/test_docker.sh
scripts/test_docker.sh -q test/test_cache_core.py
```

Le script choisit `/opt/cache-venv/bin/python` si présent, sinon `/tmp/cache-cocotb-venv/bin/python`. Le conteneur utilisé disposait de ce second environnement et de `libpython3.13`. Le `.venv` partagé de l’hôte ne convient pas au Python du conteneur. Les modifications du Dockerfile préparent les dépendances dans le dernier étage, après les compilations coûteuses ; aucune reconstruction d’image n’a été nécessaire pour cette campagne. Les installations temporaires seront à refaire si le conteneur est remplacé sans reconstruire l’image.

Versions mesurées : Cocotb 2.0.1, Verilator 5.053 devel, révision `v5.052-537-g2fa781df8`. Accès aux structs validé :

```python
dut["data_i.mem_addr"].value = 0x1000
```

`dut.data_i.mem_addr` ne fonctionne pas avec cette combinaison. `cocotb_wrapper.py` a été supprimé ; les nouveaux tests ne dépendent pas du parsing Verible ni de `generated_config.py`. Les anciens utilitaires sous `test/drivers`, `test/models` et `test/util.py` sont historiques, pas une deuxième référence validée.

Vivado utilisé sur l’hôte : `/opt/Xilinx/Vivado/2025.2/Vivado/bin/vivado`. La synthèse et le routage fonctionnaient dans l’environnement restreint ; XSim et l’accès matériel ont nécessité l’exécution hors sandbox. Un échec XSim avec exception et journal vide peut donc être environnemental. Ne pas assimiler le code retour nul d’XSim à une réussite : le script d’équivalence contrôle aussi le marqueur de succès et l’absence de fatal.

## Preuves acquises et état matériel

- 44 cas pytest réussis après la dernière modification du RTL, dont quatre géométries du cœur, erreurs et resets en cours de transferts.
- RAM RTL synthétisée en BRAM ; équivalence RTL/IP réelle passée dans XSim.
- Deux bitstreams construits avec les vraies IP MIG/horloges ; timing respecté, zéro CDC critique. Avertissements vendor résiduels explicités dans l’état de vérification.
- Chaque backend a réussi sur la Nexys Video 1781 commandes UART, 258 mots et 1000 opérations aléatoires, avec évictions sales et erreurs d’adressage.
- Dernière configuration chargée : backend RTL, en mémoire volatile uniquement. Aucune écriture flash.

Depuis cette campagne autonome, la carte a été reprogrammée avec le design
ADAM intégré, lui aussi avec le backend RAM RTL. Le dernier bitstream chargé
est donc celui d’ADAM, SHA-256 `4fae4219a27db0afe4cd4d4c3d05e6d270c3602e5f7bf3a5678e1c39499eed09`.
La programmation reste volatile.

Les SHA256 des bitstreams et résultats sont dans `VALIDATION_RESULTS.json`. Les artefacts volumineux et journaux sont sous `sim_build/`, ignoré par Git. Une modification ultérieure du RTL invalide la correspondance avec ces résultats jusqu’à nouvelle validation.

Identification lors des essais : JTAG Digilent `210276B063C4B`, UART FT232R `A904CZUE`, chemin stable `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A904CZUE-if00-port0`. Les noms ttyUSB peuvent changer. Le script de programmation cible cette carte explicitement. Les essais mémoire écrasent les adresses indiquées dans le guide carte.

## État du workspace et précautions de reprise

Aucun commit n’a été créé pendant cette intervention. De nombreuses sources ajoutées sont encore non suivies : ne pas confondre « non suivi » et « jetable ».

Des modifications préexistaient à l’intervention : notamment `Dockerfile`, `docker.sh`, `generated_config.py`, `test/conftest.py`, ainsi que des fichiers locaux `.bashrc`, `.bash_history`, `.cache`, `.venv` et une première version de la RAM et de son test. Certains de ces fichiers ont ensuite aussi été modifiés pendant le travail. Ne pas attribuer tout le diff à l’agent ni restaurer globalement le workspace.

Les sources UART/Vivado étaient en partie masquées par `.gitignore` ; l’ignore a été corrigé pour exposer les sources utiles. Les modèles `test/rtl/adam_mig_model.sv` et `clk_ref_mig_model.sv` sont uniquement fonctionnels et ne doivent jamais entrer dans un build physique. Le manifeste du cœur est `src/cache.f` ; les scripts ajoutent explicitement les sources de top et les IP nécessaires.

`src/save_controller.sv` redéfinissait un module actif : supprimé et archivé dans `docs/legacy/cache_controller_monolithic.sv.txt`. Les anciennes exemptions de lint sur les erreurs/reset/calibration et la RAM ont été retirées. Le lint brut a encore des avertissements documentés ; ne pas annoncer un lint sans avertissement.

## Suite recommandée

Commencer par `git status`, lire l’état de vérification et identifier le prochain objectif avec l’utilisateur. Ne pas reprendre l’audit historique comme si aucune correction n’existait.

Si la poursuite porte sur la fermeture complète du plan, les sujets encore ouverts sont : couverture mesurée des états/transitions/croisements, propriétés ou preuves formelles ciblées, campagnes multi-seeds plus longues, simulation quatre états du cœur complet et instrumentation des latences hit/miss/writeback. La campagne matérielle actuelle vérifie les données mais ne mesure pas ces latences, et ne relève pas directement un compteur de calibration DDR.

Pour toute modification : lancer les tests du module, puis les intégrations affectées. Pour la RAM, refaire synthèse et équivalence vendor. Pour les resets/CDC ou le top physique, refaire les rapports timing/CDC/DRC et skew. Actualiser les résultats uniquement avec les preuves réellement obtenues, en distinguant simulation, fermeture physique et essais sur carte.

Pour une modification dans `adam/`, suivre plutôt la matrice de reprise et le
plan par phases de [ADAM_INTEGRATION_HANDOFF.md](ADAM_INTEGRATION_HANDOFF.md).
Le sous-répertoire `uart_src/` est un chantier séparé pris en charge par un autre
agent ; ne pas l’inclure implicitement dans une modification ADAM/cache.
