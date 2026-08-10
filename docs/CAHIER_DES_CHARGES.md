# Cahier des Charges — Agent Smith

> Document de référence du projet. Toute section ci-dessous est directement issue du sujet officiel `en.subject_1-1.pdf` (v1.1, 42, en collaboration avec @ldevelle). Les renvois `(§X.Y)` pointent vers les chapitres correspondants du sujet pour permettre une vérification croisée à tout moment.
>
> **Champs à compléter par l'équipe** (non présents dans le sujet, donc non inventés ici) : logins des membres, dépôt Git, date de soutenance/exam, répartition des rôles.

---

## 0. Métadonnées du projet

| Champ | Valeur |
|---|---|
| Nom du projet | Agent Smith |
| École | 42 |
| Version du sujet | 1.1 |
| Membres de l'équipe | *Gaspard TOURDIAT & Kevin Bertrand* |
| Date de rendu / exam | *Estimé au 2026-09-01* |

---

## 1. Contexte et objectif général (§I, §III)

Le projet consiste à construire un **framework agentique** capable de résoudre de manière autonome des problèmes de programmation. L'agent doit :

- Raisonner sur une tâche de code (« Thought »)
- Générer du code Python exécutable (« Code »)
- L'exécuter dans un environnement sandboxé et observer le résultat (« Observation »)
- Itérer jusqu'à obtenir une solution ou atteindre une limite

Le système est évalué sur deux benchmarks distincts :

- **MBPP** (Mostly Basic Python Problems) — problèmes algorithmiques Python (§V.3)
- **SWE-bench** — correction de bugs réels dans des dépôts de production, exécutés dans des conteneurs Docker (§V.4)

L'objectif pédagogique n'est pas seulement de rendre l'agent « intelligent », mais de le rendre **sûr, contrôlé, reproductible et mesurable** (§III).

---

## 2. Cadre d'usage de l'IA (§II)

Le sujet impose un cadre explicite sur l'usage d'outils IA pendant le développement :

- L'IA est un partenaire, jamais un décideur : l'équipe reste seule responsable des choix techniques et doit pouvoir les expliquer en soutenance.
- Toute utilisation d'IA doit être **documentée et transparente** (voir §8 README ci-dessous — section « Resources »).
- Mauvaise pratique explicitement citée par le sujet : faire générer l'architecture entière par une IA sans pouvoir la justifier en revue.

---

## 3. Règles générales et contraintes techniques (§IV)

### 3.1 Règles générales (§IV.1)
- Python **3.10** obligatoire
- Gestionnaire de paquets **uv** obligatoire
- Architecture logicielle « clean » (séparation des responsabilités)
- Gestion **gracieuse** de toutes les erreurs — un crash pendant l'évaluation = échec
- Code lisible, structuré, documenté
- Toute exécution de code généré par le LLM doit avoir lieu dans le sandbox

### 3.2 Contraintes techniques (§IV.2)
- Support de **plusieurs providers et modèles LLM**
- Suivi d'usage obligatoire : tokens, retries, latence, nombre de requêtes
- Sandbox **configurable** (imports, accès filesystem) — cf. §5
- Les outils (tools) doivent fonctionner indépendamment de la boucle agent
- **Interdiction** d'utiliser une librairie qui réimplémente une logique d'orchestration d'agents : `llama-index`, `smolagents`, `langgraph`, `crewai`, `autogen`
- La boucle agent doit être une implémentation **maison**
- Une architecture multi-agents est autorisée mais l'orchestration doit rester du code propre à l'équipe

---

## 4. Framework agentique (§V.1)

Le système doit implémenter une boucle **Thought → Code → Observation** :

1. Extraction du code Python généré par le LLM depuis sa réponse
2. La couche d'extraction doit gérer plusieurs formats de sortie (non exhaustif) :
   - blocs ```` ```python ... ``` <end_code> ```` (format principal)
   - appels d'outils XML façon Anthropic (`<invoke name="..."><parameter>...`)
   - appels JSON/Hermes (`<tool_call>{"name": ..., "arguments": ...}</tool_call>`)
   - format ReAct (`Action: tool_name` / `Action Input: {...}`)
   - Les formats non-Python doivent être convertis en appels de fonction Python équivalents avant exécution
3. Exécution du code dans le sandbox
4. Réinjection du résultat d'exécution dans le contexte du LLM
5. Résolution autonome des tâches via la boucle
6. Conception du **system prompt** : documentation des outils disponibles, exemples de structure de réponse (Thought/Code/Observation), exemples de boucles de raisonnement efficaces

Le sandbox doit fournir un **feedback explicite** au LLM dans chacun des cas suivants (aucun échec silencieux toléré) :
- Aucun bloc de code valide trouvé
- Bloc de code malformé mais interprété quand même (comportement à documenter)
- Timeout d'exécution atteint (sortie partielle)
- Sortie d'un outil tronquée pour cause de taille
- Une édition introduit une erreur de syntaxe ou une violation de lint

### 4.1 Démarche de développement conseillée (§V.1.1)
Le sujet fournit explicitement une série de questions de guidage (à utiliser comme grille d'auto-évaluation, pas comme exigence notée) :
- Quel benchmark est le plus simple et doit être attaqué en premier ?
- Le système est-il testé avec le modèle le plus capable disponible avant d'ajouter des contraintes ?
- L'agent résout-il la tâche la plus simple sans limites de tokens/itérations ?
- Que se passe-t-il dans les 3 à 5 premières itérations ? (tool calling, hallucination, chemin inattendu)
- La tâche a-t-elle été résolue manuellement par un humain avant d'écrire le prompt ?
- L'agent généralise-t-il, ou y a-t-il eu sur-ajustement (overfitting) à une tâche précise ?

---

## 5. Le Sandbox (§V.2)

### 5.1 CLI attendue
```bash
uv run sandbox                                              # mode interactif (REPL)
uv run sandbox sandbox_template.json                        # config custom
uv run sandbox --mcp-stdio "python mcp_tools_mbpp.py" sandbox_template.json
uv run sandbox --mcp-server <URL>                            # HTTP
uv run sandbox --mcp-stdio "python mcp_tools_swebench.py" sandbox_template.json
```
Le mode interactif (sans tâche) doit ouvrir un prompt REPL, exécuter chaque entrée dans le namespace du sandbox (mêmes restrictions que §5.3), afficher résultat ou erreur, et se terminer proprement sur `exit` ou EOF (Ctrl+D).

### 5.2 `final_answer`
- Fonction **injectée par le sandbox**, toujours disponible, quel que soit le serveur MCP connecté.
- **Ce n'est pas un outil MCP.**
- MBPP : `final_answer(votre_code_solution)`
- SWE-bench : `final_answer(get_patch())`
- Distinction architecturale à respecter : les wrappers d'outils MCP sont découverts dynamiquement depuis le serveur connecté ; `final_answer` reste constant.
- `KeyboardInterrupt` et `SystemExit` ne doivent **jamais** être capturés silencieusement — ils doivent remonter jusqu'à la boucle agent.

### 5.3 Contraintes de sécurité obligatoires
- **Imports** : uniquement les modules de l'allowlist configurée
- **Filesystem** : accès limité aux répertoires de `allowed_directories` (chemins vus par le process sandbox lui-même, pas seulement côté host)
- **Réseau** : aucune connexion sortante ou entrante autorisée
- **Timeout d'exécution** : code dépassant le timeout configuré est terminé (s'applique uniquement au code exécuté *dans* le sandbox, pas aux actions du serveur MCP)
- **Mémoire** : code dépassant la RAM autorisée est terminé
- **Builtins restreints** : retrait/override des builtins dangereux

Implémentation avec uniquement les librairies standard Python — **`RestrictedPython` et équivalents externes sont interdits**.

### 5.4 Configuration (modèles Pydantic obligatoires)
```python
class SandboxConfig(BaseModel):
    authorized_imports: List[str] = [...]   # allowlist, tout le reste est bloqué par défaut
    allowed_directories: List[str] = ["/testbed", "/tmp/agent"]
    max_execution_time_seconds: int = 30
    max_memory_mb: int = 512
```

### 5.5 Intégration MCP
- Outils obligatoires exposés via un serveur MCP (Model Context Protocol)
- Outils, ressources et prompts MCP doivent être exposés
- Les outils MCP doivent être appelables comme des fonctions Python depuis le sandbox
- Le système sera testé avec un **serveur MCP inconnu** → l'implémentation doit être générique, pas hardcodée sur les seuls outils fournis
- Fichiers `mcp_tools_mbpp.py` et `mcp_tools_swebench.py` **à la racine du dépôt**
- Support obligatoire des transports **stdio** ET **HTTP streamable**

### 5.6 Manuel du sandbox
Généré **dynamiquement** depuis les schémas d'outils du serveur MCP connecté (noms, descriptions, types de paramètres). Doit être fourni au LLM dans le prompt système et se mettre à jour automatiquement si le serveur MCP change.

---

## 6. Agent MBPP (§V.3)

### 6.1 CLI
```bash
cd moulinette && uv run moulinette_eval dump mbpp --output ../cache/mbpp_task.json
cd ../student && uv run python -m agent_mbpp --task-file ../cache/mbpp_task.json \
  --output ../cache/mbpp_solution.json --model-name "model/name" --provider-url "https://provider.api/v1"
cd ../moulinette && uv run moulinette_eval validate mbpp ../cache/mbpp_task.json ../cache/mbpp_solution.json
```

### 6.2 Outils MCP MBPP
- `run_tests` obligatoire
- Outils additionnels libres

### 6.3 Modèles Pydantic obligatoires
- `MBPPTaskInput` (task_id, task_definition, function_definition, test_imports, test_list)
- `StepMetrics` (step, input_tokens, output_tokens, request_time_ms, api_url, model_name, llm_output, sandbox_input, sandbox_output, retries, timestamp)
- `SolutionOutput` (task_id, benchmark, success, solution, system_prompt, iterations, total_requests, total_input_tokens, total_output_tokens, total_time_seconds, steps, error, timestamp)

`max_iterations` doit être un paramètre configurable de la boucle agent.

---

## 7. Agent SWE-bench (§V.4)

- Résolution de bugs réels dans des dépôts, dans des conteneurs **Docker**
- Deux architectures valides : (a) sandbox déployé dans le conteneur, ou (b) sandbox sur l'hôte avec des outils MCP qui font le pont vers Docker — dans les deux cas les contraintes de sécurité du sandbox s'appliquent
- Génération de patch via `git -c core.fileMode=false diff`
- Nettoyage des conteneurs Docker **à la charge de l'équipe** après exécution
- Tâches suggérées pour les premiers tests : `sympy__sympy-14711`, `sympy__sympy-13480`, `pydata__xarray-4629`

### 7.1 CLI
```bash
cd moulinette && uv run moulinette_eval dump swebench --output ../cache/swebench_task.json
cd ../student && uv run python -m agent_swebench --task-file ../cache/swebench_task.json \
  --output ../cache/swebench_solution.json --model-name "model/name" --provider-url "https://provider.api/v1"
cd ../moulinette && uv run moulinette_eval validate swebench ../cache/swebench_task.json ../cache/swebench_solution.json
```

### 7.2 Modèles Pydantic obligatoires
- `SWEBenchTaskInput` (instance_id, problem_statement, docker_image, eval_script, hints_text, repo)
- `StepMetrics` et `SolutionOutput` — mêmes champs que MBPP, avec en plus `system_prompt` obligatoire dans `SolutionOutput` pour traçabilité complète du raisonnement (voir §10, AI Safety)

---

## 8. Outils obligatoires du serveur MCP (§V.5)

Testés **indépendamment**, dans le contexte SWE-bench.

### 8.1 Système de fichiers
- `read_file(filepath, start_line, end_line)` — sortie façon `cat -n` : `<n°ligne>: <contenu>`
- `edit_file(filepath, old_str, new_str)` — remplacement de chaîne exacte
- `list_files(directory, pattern)`

### 8.2 Recherche de code
- `search_code(pattern, file_pattern)` — sortie façon grep : `/chemin/absolu.py:<ligne> <contenu>`
- `search_function_or_class_definition_in_code(name)` — même format de sortie
- `find_references(name, filepath, line)` — même format de sortie

### 8.3 Exécution
- `run_tests()` — exécute le script d'évaluation
- `get_patch()` — récupère le diff git unifié des changements
- `run_command(command, workdir)` — exécute une commande shell, retourne stdout/stderr/exit code

---

## 9. Providers LLM (§V.6)

- Support **multi-providers et multi-modèles** obligatoire
- **Uniquement des tiers gratuits** : aucun plan payant, crédit acheté, ou compte facturable
- **Multi-token obligatoire** : plusieurs clés API par provider, avec **rotation** en cas de rate limit / quota épuisé
- Abstraction suffisante pour changer de provider sans refactoring majeur (le choix du provider n'est **pas noté**, la qualité de l'abstraction l'est)
- Utiliser les `stop_sequences` pour empêcher le modèle de générer de faux résultats d'outils après un appel (hallucination de sortie d'exécution)
- Exemples de providers gratuits cités (liste non exhaustive et non contractuelle) : OpenRouter, Together AI, Groq, Google AI Studio, Mistral AI, Cohere, Fireworks AI, Perplexity AI, Anyscale

---

## 10. Rapport de benchmark de modèles (§V.7)

Fichier **`BENCHMARK_REPORT.md`** à la racine du dépôt, comparant **au moins 5 modèles** sur **au moins 3 tâches SWE-bench** communes.

Doit inclure :
1. **Setup** : modèles/providers comparés, tâches utilisées, justification du choix des tâches
2. **Tableau de résultats** par couple modèle × tâche : Pass/Fail, itérations, tokens input/output, temps
3. **Fiabilité provider** par modèle : temps de réponse moyen, nombre de retries, disponibilité globale
4. **Métriques intermédiaires** (au moins 2 parmi) : étape de première lecture/édition du fichier apparaissant dans le patch final ; étape où les échecs de tests commencent à diminuer ; itérations entre premier passage des tests et `final_answer`
5. **Étude d'ablation** : au moins une comparaison avant/après d'un changement (prompt, outils, paramètres) sur les mêmes tâches et le même modèle
6. **Conclusions** : modèle(s) retenu(s) pour le pipeline final et pourquoi, modèles écartés et pourquoi — basé sur les données recueillies

Les fichiers `solution.json` sous-jacents doivent être présents dans le dépôt.

---

## 11. Évaluation — limites strictes (§VI)

Les clés API sont fournies via un fichier `.env` :
```bash
./exam_TYPE.sh --student-path ./student --moulinette-path ./moulinette --envfile /path/to/.env
```

| Script | Tâches | Seuil de réussite |
|---|---|---|
| `exam_mbpp.sh` | 5 tâches aléatoires | 4/5 |
| `exam_swebench.sh` | 3 tâches aléatoires | 2/3 |
| `exam_sandbox.sh` | Tests de sécurité | TOUS |

### 11.1 Limites MBPP
| Métrique | Limite |
|---|---|
| Itérations max | 10 |
| Tokens input max | 6 000 |
| Tokens output max | 1 500 |
| Timeout | 120 s |

### 11.2 Limites SWE-bench
| Métrique | Limite |
|---|---|
| Itérations max | 30 |
| Tokens input max | 300 000 |
| Tokens output max | 10 000 |
| Timeout | 900 s |

- Les limites de tokens sont **cumulatives** sur toutes les itérations d'une même tâche
- Les tokens de raisonnement (modèles « reasoning ») comptent dans la limite
- **Aucun retry autorisé pendant l'examen**

### 11.3 Critères de validation globaux (§VI.3)
Pour valider le projet, il faut **simultanément** :
- Respecter les seuils de réussite MBPP ET SWE-bench
- Respecter toutes les limites d'itérations/tokens/timeout
- Faire passer tous les outils obligatoires aux tests indépendants
- Faire passer au sandbox les tests d'isolation et de sécurité

**Point bloquant explicite** : toute clé API en dur dans le code source = échec de sécurité automatique. Les clés doivent venir de variables d'environnement / fichier `.env`.

### 11.4 Ce qui sera testé en soutenance (§VI.4)
- Correction des outils obligatoires
- Implémentation correcte de la boucle de raisonnement
- Garanties de sécurité et d'isolation du sandbox
- Résultats de benchmark de modèles et statistiques de tokens
- Qualité de code, robustesse, architecture globale
- **Modifications live** demandées pendant la soutenance sur une tâche MBPP (2 à 5 min par modification attendue) — teste la compréhension réelle du code, à annuler ensuite via `git checkout`

### 11.5 Sécurité IA — garde-fous stricts (§VI.4.1)
L'agent **ne doit pas** :
- Récupérer des solutions depuis des pull requests, issues, ou sources externes
- Utiliser des patchs mémorisés dans les données d'entraînement sans exploration réelle
- Contourner les contraintes de sécurité du sandbox
- Accéder à des ressources hors du contexte de la tâche fournie

**Toute violation entraîne une note de 0.** Les champs `system_prompt`, `llm_output`, `sandbox_input`, `sandbox_output` existent précisément pour permettre la traçabilité du raisonnement.

### 11.6 Structure de logging (§VI.5)
```
./evaluations/EVAL_TYPE/YYYY-MM-DD_HH-MM-SS/task_id/task.json, solution.json, stdout.log, stderr.log
```

---

## 12. Exigences du README (§VII)

Fichier **`README.md`** à la racine, en **anglais**, incluant au minimum :

- **1ère ligne**, en italique : *This project has been created as part of the 42 curriculum by \<login1\>[, \<login2\>[, ...]].*
- Section **« Description »** : présentation claire du projet, objectif, aperçu
- Section **« Instructions »** : compilation, installation, exécution
- Section **« Resources »** : références classiques (doc, articles, tutoriels) **+ description de l'usage de l'IA** (pour quelles tâches, quelles parties du projet)
- Sections additionnelles **obligatoires pour ce projet précis** :
  - System architecture
  - Agent loop explanation
  - Sandbox design
  - Tool implementation details
  - Benchmark results and analysis

---

## 13. Soumission (§VIII)

- Dépôt Git, structure interne libre
- Fichiers de configuration sandbox et modèles inclus
- `README.md` présent
- **Ne pas inclure** : images Docker, poids de modèles volumineux, sorties générées

---

## 14. Synthèse des livrables attendus

| # | Livrable | Emplacement | Référence sujet |
|---|---|---|---|
| 1 | Boucle agent (Thought→Code→Observation) | code source | §V.1 |
| 2 | Sandbox sécurisé + CLI + REPL | code source, `sandbox` | §V.2 |
| 3 | `mcp_tools_mbpp.py` | racine du dépôt | §V.2, §V.3 |
| 4 | `mcp_tools_swebench.py` | racine du dépôt | §V.2, §V.4 |
| 5 | `agent_mbpp` (module CLI) | `student/` | §V.3 |
| 6 | `agent_swebench` (module CLI) | `student/` | §V.4 |
| 7 | 8 outils MCP obligatoires | serveur MCP | §V.5 |
| 8 | Gestion multi-provider / multi-clé LLM | code source | §V.6 |
| 9 | `BENCHMARK_REPORT.md` (≥5 modèles × ≥3 tâches) | racine du dépôt | §V.7 |
| 10 | `README.md` (EN, sections imposées) | racine du dépôt | §VII |
| 11 | Fichiers de config sandbox/modèles (JSON/Pydantic) | racine ou `config/` | §V.2.4 |

---

*Ce cahier des charges est une reformulation structurée et traçable du sujet officiel. En cas de doute ou de contradiction apparente, le fichier `subject-1-1.txt` (extraction du PDF officiel) fait foi.*
