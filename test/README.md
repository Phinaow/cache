# Vérification du cache

La régression utilise Cocotb 2.0.1 et Verilator dans le conteneur `cache_design`. Chaque top/configuration est compilé dans un répertoire distinct sous `sim_build/tests/`. Les assertions SystemVerilog sont activées, les options de traces existantes sont conservées.

## Commande dans le conteneur actuel

Depuis la racine du projet sur l’hôte :

```bash
docker exec -w /phinaow cache_design bash -lc '
  export LIBPYTHON_LOC=/usr/lib/x86_64-linux-gnu/libpython3.13.so.1.0
  export PYTHONPATH=/phinaow:/phinaow/test
  /tmp/cache-cocotb-venv/bin/python -m pytest -q test
'
```

Le conteneur actuel possède ses dépendances dans `/tmp/cache-cocotb-venv`. Après reconstruction avec le Dockerfile modifié, utiliser `/opt/cache-venv/bin/python`. Il n’est pas nécessaire de reconstruire pour utiliser le conteneur courant.

Pour cibler un module, remplacer `test` par exemple par `test/test_transaction.py`. `-s` affiche le détail du simulateur. Les VCD (`dump.vcd`), binaires et résultats XML se trouvent sous `sim_build/tests/<top>[_configuration]/`.

## Style et organisation

Les commentaires et docstrings du code sont en anglais. La documentation peut rester en français. Un fichier correspond à un module et expose des scénarios nommés. Le banc local contient seulement les opérations nécessaires : cycle, reset, commande et référence. Les observations utilisent des noms explicites ; les assertions sont proches du comportement contrôlé. Les boucles sont bornées et les seeds fixes.

Les auxiliaires partagés ont un rôle précis :

- `cpu_master.py` : maître AXI-Lite qui peut attendre VALID avant READY et modifie les entrées après leur acceptation ; vérifie les réponses bloquées.
- `axi_memory.py` : mémoire AXI par octet, pauses, erreurs de réponse et IDs ; utilisée pour les moteurs et le cœur.
- `axi_lite_slave.py` : esclave AXI-Lite indépendant pour les ponts UART, avec AW/W séparés et B retardé.
- `serial_link.py` : source et décodeur 8N1 indépendants du RTL UART.

Le banc writeback reste l’exemple de référence : observation des signaux avant le front, sortie du modèle RAM mise à jour après le front, puis scénarios explicites. Il ne remplace pas une RAM synchrone par une lecture combinatoire.

## Structs natifs

Validé avec Verilator `5.053 devel` (`v5.052-537-g2fa781df8`) et Cocotb `2.0.1` :

```python
dut["data_i.mem_addr"].value = 0x1000
dut["data_i.nb_transfer"].value = 63
dut["data_i.cache_addr"].value = 17
dut["data_i.wb_rf"].value = 1
```

Aucun wrapper, parsing Verible ou `commit()` n’est nécessaire. `dut.data_i.mem_addr` n’est pas supporté par cette combinaison ; le nom VPI complet fonctionne. `test_struct_access.py` contrôle la lecture/écriture des champs et la conservation des voisins. Les outils Verible historiques sont conservés mais ne sont plus utilisés par les tests.

## Résultats et périmètre

La régression complète a passé **44 cas pytest**, avec plusieurs scénarios Cocotb dans certains cas. Elle couvre le cœur, les périphériques UART et les tops. Les configurations de FIFO, de buffers et de PLRU sont paramétrées ; le cache complet est testé en 8 Kio / 8 lignes, 1 Kio / 1 ligne, 512 octets / 2 lignes et 1 Kio / 4 lignes. La matrice et les limites sont détaillées dans [MODULES.md](../docs/MODULES.md).

La comparaison RTL/IP utilise le véritable modèle Block Memory Generator dans XSim, en complément de Cocotb/Verilator :

```bash
vivado -mode batch -source scripts/create_ram_ip.tcl
vivado -mode batch -source scripts/simulate_ram_backends.tcl
```

Les tests de `top_cache` et `uart_to_cache` utilisent des substituts fonctionnels du MIG et du clock wizard. Ils contrôlent le câblage, les resets et les transactions, pas le timing ni la calibration électrique DDR3. Ces substituts sont exclus des scripts de construction matérielle.

Les anciens modèles/pilotes sous `test/models`, `test/drivers` et `test/util.py` ne sont plus dans le chemin des nouveaux tests ; ils ne constituent pas une deuxième référence validée.
