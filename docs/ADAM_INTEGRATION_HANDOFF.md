# Passation de l’intégration du cache dans ADAM

État de référence : 23 octobre 2026. Ce document est le point d’entrée pour
un nouvel agent qui reprend l’intégration dans `/home/johann/cache/adam`.

## Résultat atteint

Le cache DRAM a été intégré au SoC ADAM, simulé avec Cocotb/Verilator,
synthétisé et routé dans Vivado 2025.2, puis testé sur une Nexys Video. Le
bitstream validé est actuellement chargé dans le FPGA de manière volatile ; il
n’a pas été écrit en flash.

Configuration testée :

| Élément | Valeur |
|---|---|
| CPU high-speed domain | CV32E40P, `ADAM_CORE_CPU=adam_core_cv32e40p` |
| CPU low-power domain | Ibex, `ADAM_CORE_LPCPU=adam_core_ibex` |
| Interface CPU/cache | AXI-Lite, 32 bits |
| Interface cache/MIG | AXI, 128 bits |
| Fenêtre DDR globale | `[0x50000000, 0x70000000[` (512 Mio) |
| Cache | 8 Kio, 8 lignes de 1 Kio, fully associative |
| Politique | write-back, write-allocate, tree-PLRU, bloquant |
| RAM du cache | backend RTL, `USE_VENDOR_RAM=0`, 16 RAMB18 |
| Carte | Nexys Video, xc7a200t, JTAG `210276B063C4B` |
| UART de test | FT232R `A904CZUE`, 115200 8N1 |

## Ordre de lecture

1. Ce document, puis `git status` à la racine et dans `adam/`.
2. [`adam/docs/DRAM_INTEGRATION.md`](../adam/docs/DRAM_INTEGRATION.md) pour les
   choix d’architecture, les modifications et les avertissements.
3. [`adam/docs/DRAM_BOARD_RESULTS.json`](../adam/docs/DRAM_BOARD_RESULTS.json)
   pour les résultats et empreintes exactes.
4. [`adam/docs/BOARD_TEST.md`](../adam/docs/BOARD_TEST.md) pour reproduire le
   flot Vivado, la programmation et le test matériel.
5. [`CACHE_CONTRACT.md`](CACHE_CONTRACT.md), puis les sources sous
   `adam/rtl/dram/` et les tests sous `adam/test/dram/`.

Le document historique `adam/docs/DRAM_SYNTHESIS_RESULTS.json` décrit la
première synthèse avant les corrections physiques. Pour l’état actuel, utiliser
`DRAM_BOARD_RESULTS.json`.

## Chemin des transactions

Le bootloader s’exécute sur le CV32E40P du high-speed domain. Ses accès suivent :

```text
CV32E40P
  -> adaptateur CPU/fabric ADAM
  -> fabric AXI-Lite high-speed domain
  -> port HSEXT
  -> adam / adam_top
  -> top_cache
  -> cache_core
  -> MIG AXI
  -> DDR3 Nexys Video
```

La fabric reconnaît la fenêtre globale DDR et soustrait une seule fois la base
`0x50000000`. Le cache voit donc une adresse locale comprise entre
`0x00000000` et `0x1FFFFFFF`. Une adresse à partir de `0x70000000` ne doit pas
sélectionner HSEXT.

Le protocole du bootloader ADAM n’est pas celui du module autonome
`uart_to_axi` sous `uart_src/`. Le port série transporte les commandes du
bootloader ; c’est le CPU qui produit les transactions AXI-Lite. `uart_src/` est
un chantier séparé et ne doit pas être modifié pour poursuivre ADAM.

## Modifications réalisées dans ADAM

### Mapping et génération

- Ajout de `en_hsext` dans la configuration ADAM, désactivé par défaut.
- Activation explicite sur les cibles Nexys Video concernées.
- Ajout de la région linker HSEXT de 512 Mio et du pointeur RAL correspondant.
- Ajout du décodage HSEXT et de la translation d’adresse dans
  `rtl/fabric/adam_fabric_hsdom.sv`.
- Propagation du bus externe dans `adam_fabric`, `adam`, `adam_top` et les
  utilisateurs historiques qui doivent au minimum raccorder le nouveau port.

### Cache, MIG et horloges

- Import sans modification interne des quatorze fichiers du cache sous
  `adam/rtl/dram/`. Leur identité est contrôlée par
  `adam/rtl/dram/UPSTREAM_SHA256.json` et un test de provenance.
- Ajout d’une bibliothèque CMake distincte pour le RTL du cache.
- Instance directe de `top_cache` dans `fpga/adam_nexys_video.sv`.
- Ajout du clock wizard 50/100/200 MHz et utilisation du vrai MIG physique.
- Horloge CPU/cache côté CPU : 50 MHz. Domaine mémoire du cache : `ui_clk`
  fourni par le MIG.
- Ajout des contraintes tardives `fpga/cache_cdc.xdc` pour les deux mailboxes.

### Resets, GPIO et synthèse physique

- Le reset du cache dépend directement du reset global et du verrouillage du
  clock wizard ; le reset CPU temporisé ne traverse plus vers le MIG.
- Le relâchement du reset JTAG est synchronisé localement sur deux fronts TCK
  avec attribut `ASYNC_REG`.
- Suppression des tie-offs constants qui entraient en conflit avec les sorties
  GPIO 1 à 7. Les interfaces GPIO lisent maintenant les broches d’entrée
  externes, et non un rebouclage de leur sortie.
- Sélection des primitives Xilinx Ibex avec
  `PRIM_DEFAULT_IMPL=prim_pkg::ImplXilinx`, ce qui évite les boucles de latch
  de clock gating générique.

### Infrastructure de vérification ajoutée

| Fichier | Rôle |
|---|---|
| `adam/scripts/test_dram_docker.sh` | Lance les tests ADAM dans `cache_design` |
| `adam/test/dram/` | Tests du cœur, top, fabric/configuration et reset top |
| `adam/scripts/prepare_dram_synth.py` | Prépare et empreinte les 354 entrées physiques |
| `adam/scripts/synth_dram.tcl` | Synthèse et, avec `impl`, implémentation complète |
| `adam/scripts/resume_dram.tcl` | Reprend un projet interrompu sans refaire les IP terminées |
| `adam/scripts/check_dram_reports.py` | Refuse timing, CDC/DRC critiques, skew ou contraintes incomplets |
| `adam/scripts/test_dram_board.py` | Teste SRAM et DDR via le bootloader CPU ADAM |

Les modèles `adam/test/dram/rtl/adam_mig_model.sv` et
`adam_top_stub.sv` sont réservés à la simulation. Ils ne doivent jamais être
ajoutés à une construction physique.

## Preuves actuelles

### Simulation

La dernière régression compte 11 cas pytest réussis. Elle couvre les quatre
configurations du cœur, les erreurs et resets AXI, le top avec calibration MIG,
le trajet fabric/cache, la configuration activée et désactivée, la provenance
des sources, ainsi que les GPIO et resets de `adam_top`.

```bash
cd /home/johann/cache/adam
scripts/test_dram_docker.sh
```

Journal : `adam/sim_build/dram_board_regression_2026-10-23.log`.

### Implémentation physique

Campagne : `adam/sim_build/vivado/dram_board_2026-10-23/`.

| Mesure post-route | Valeur |
|---|---:|
| Setup slack | +0,037 ns |
| Hold slack | +0,008 ns |
| Pulse slack | 0,000 ns |
| Endpoints en échec | 0 |
| CDC critiques | 0 |
| DRC critiques | 0 |
| Skew des deux mailboxes | +8,904 / +9,148 ns |
| SoC complet | 34 692 LUT, 21 116 FF, 264 RAMB36, 16 RAMB18, 6 DSP |

Les avertissements non critiques restent visibles : deux `CDC-2` et 75
`CDC-15` dans le DMI/JTAG, deux `CDC-8` dans les synchroniseurs internes du
MIG, des DRC vendor/MIG/DSP/JTAG, des resets asynchrones commandant les RAM
internes historiques d’ADAM, et deux bits DMI sans charge (`RTSTAT-10`). Ils ne
touchent pas les mailboxes du cache et ne sont pas masqués globalement. La marge
setup est positive mais faible ; tout changement physique impose un nouveau
routage.

### Carte

Le bitstream suivant a été programmé de façon volatile :

```text
SHA-256 4fae4219a27db0afe4cd4d4c3d05e6d270c3602e5f7bf3a5678e1c39499eed09
```

Le test via le bootloader CV32E40P a réussi 1 156 commandes en 35,905 s :

- SRAM interne de contrôle ;
- 32 lignes DDR, donc plus que les huit voies, avec évictions sales ;
- stores byte sur toutes les lanes et motifs de modifications partielles ;
- sentinelles à `0x50000000`, `0x58000000`, `0x60000000`, `0x68000000` et
  `0x6FFFFFFC` pour détecter les alias ;
- 1 000 lectures/écritures mixtes avec seed fixe `0xADA2026` ;
- relecture finale de 32 784 octets DDR et contrôle des CRC.

La carte reste chargée avec ce design tant qu’elle n’est pas éteinte,
réinitialisée au niveau FPGA ou reprogrammée.

## Commandes de reprise

Depuis `/home/johann/cache/adam` :

```bash
# Régression ADAM.
scripts/test_dram_docker.sh

# Nouvelle campagne physique.
python3 scripts/prepare_dram_synth.py --output sim_build/vivado/<campagne>
/opt/Xilinx/Vivado/2025.2/Vivado/bin/vivado -mode batch \
  -source scripts/synth_dram.tcl \
  -tclargs "$PWD/sim_build/vivado/<campagne>" impl

# Reprise après interruption et contrôle des rapports.
/opt/Xilinx/Vivado/2025.2/Vivado/bin/vivado -mode batch \
  -source scripts/resume_dram.tcl \
  -tclargs "$PWD/sim_build/vivado/<campagne>"
python3 scripts/check_dram_reports.py sim_build/vivado/<campagne> \
  --output sim_build/vivado/<campagne>/physical_checks.json
```

La programmation et le test sur carte sont détaillés dans
`adam/docs/BOARD_TEST.md`. Les accès JTAG et série peuvent nécessiter une
autorisation hors sandbox. Utiliser `/dev/serial/by-id/` et ne jamais supposer
un numéro `ttyUSB`. Ne pas programmer la flash par défaut.

## Workspace et reproductibilité

- Aucun commit n’a été créé. Le clone ADAM contient de nombreux fichiers
  modifiés ou non suivis qui constituent l’intégration ; ne pas les nettoyer.
- Des sous-modules ADAM étaient déjà sales (`axi`, `common_cells`, `cv32e40x`,
  `riscv-dbg`). Ne pas restaurer globalement leur état.
- Le commit de base ADAM est
  `785333c9908751c419ff4d553b8b68c280c4771a`.
- `requirements.txt` à la racine contient maintenant `Jinja2==3.1.2`. La
  dépendance a aussi été installée temporairement dans le conteneur courant ;
  l’image devra être reconstruite pour la rendre pérenne après remplacement.
- La campagne physique réutilise les sources Ibex et la ROM bootloader déjà
  préparées sous `adam/work/build`. Ce n’est pas une construction CMake fraîche.
- Les résultats sous `sim_build/` sont ignorés par Git. Les JSON sous
  `adam/docs/` conservent leurs empreintes, pas les artefacts volumineux.

## Limites fonctionnelles à conserver

- Le reset invalide le cache et perd les lignes sales ; aucun flush implicite.
- Aucune cohérence n’est assurée avec un autre maître qui contournerait le cache.
- Le cache est bloquant et ne traite qu’une opération à la fois.
- Le bootloader ne remonte pas proprement les réponses AXI d’erreur ; les
  adresses invalides et erreurs mémoire sont donc injectées en simulation.
- Les stores byte matériels couvrent toutes les lanes, mais pas les seize
  valeurs WSTRB en une transaction unique. Les masques restent couverts en
  simulation.
- Les interactions reset pendant trafic, pause/clock gating et concurrence
  simultanée de plusieurs maîtres ne sont pas validées sur la carte.

## Plan de poursuite

### Phase 1 : reproductibilité de la construction

**Objectif :** supprimer la dépendance aux artefacts préparés.
**Effort relatif :** grand.
**Jalon :** build CMake frais produisant le même top et un bootloader exécutable.

| Tâche | Effort | Dépendance | Chemin critique |
|---|---:|---|---|
| Inventorier les outils RISC-V et versions requises | Petit | Aucune | Oui |
| Reconstruire Ibex, configuration et bootloader | Grand | Inventaire | Oui |
| Comparer manifeste et mapping mémoire au build validé | Moyen | Reconstruction | Oui |
| Relancer les 11 tests ADAM | Petit | Reconstruction | Non |

### Phase 2 : nouvelle preuve physique

**Objectif :** rattacher une preuve complète au build frais.
**Effort relatif :** moyen.
**Jalon :** rapports Vivado acceptés et nouveau bitstream empreinté.

| Tâche | Effort | Dépendance | Chemin critique |
|---|---:|---|---|
| Préparer la nouvelle campagne et vérifier ses empreintes | Petit | Phase 1 | Oui |
| Synthétiser, placer et router | Grand | Préparation | Oui |
| Examiner timing, CDC, DRC et skew sans masquer les warnings | Moyen | Routage | Oui |
| Comparer ressources et marges au résultat actuel | Petit | Rapports | Non |

### Phase 3 : validation système étendue

**Objectif :** couvrir les risques non observables par le test actuel.
**Effort relatif :** grand.
**Jalon :** rapport séparant clairement simulation, propriétés physiques et carte.

| Tâche | Effort | Dépendance | Chemin critique |
|---|---:|---|---|
| Reprogrammer la carte avec le nouveau SHA et rejouer la campagne | Moyen | Phase 2 | Oui |
| Ajouter un programme CPU pour erreurs AXI et resets contrôlés | Grand | Build frais | Non |
| Tester resets pendant trafic et perte/reprise de calibration | Grand | Instrumentation | Non |
| Ajouter télémétrie hit/miss/writeback et latences si requise | Grand | Contrat à définir | Non |
| Actualiser JSON et documentation avec le nouveau bitstream | Petit | Tous les tests | Oui |

Le chemin critique est : environnement reproductible → build CMake frais →
manifeste physique → routage → contrôles → programmation → archivage.
Une modification RTL ou de contraintes invalide toutes les preuves situées en
aval et impose de repartir au minimum de la régression concernée.
