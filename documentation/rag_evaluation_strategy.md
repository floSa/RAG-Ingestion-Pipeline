# Stratégie d'évaluation RAG

> **Statut du document : plan pour l'autre dépôt, `rag-agent-chat`.** Cette
> stratégie décrit l'évaluation de bout en bout du système RAG (retrieval,
> reranking, génération). Elle n'est pas mise en œuvre dans ce dépôt : la
> génération vit dans `rag-agent-chat`, et ce pipeline n'appelle aucun LLM.
>
> Ce qui existe dans ce dépôt est une mesure du **rappel dense seul** : le jeu
> de questions `documentation/campagnes/2026-09-02-jeu-de-questions.yaml`
> (30 questions), l'instrument `scripts/campagne/mesurer-le-rappel-vectoriel.py`
> et son vérificateur `scripts/campagne/verifier-le-jeu-de-questions.py`. La
> commande et la dernière mesure sont au
> [§4.7 de livraison.md](livraison.md#47-le-jeu-de-questions-et-le-rappel-vectoriel).

## Objectif

Mesurer la qualité du système RAG complet, couche agent comprise. L'évaluation
porte sur la pertinence du retrieval **et** la fidélité des réponses générées.

## Framework recommandé

**Ragas** (https://docs.ragas.io), framework open-source d'évaluation RAG.

## Métriques cibles

| Métrique            | Description                                           | Seuil cible |
|---------------------|-------------------------------------------------------|-------------|
| faithfulness        | La réponse est-elle fidèle au contexte récupéré ?     | >= 0.85     |
| context_precision   | Les chunks récupérés sont-ils pertinents ?            | >= 0.80     |
| context_recall      | Tous les éléments nécessaires sont-ils récupérés ?    | >= 0.75     |
| answer_relevancy    | La réponse répond-elle à la question ?                | >= 0.85     |
| answer_correctness  | La réponse est-elle factuellement correcte ?          | >= 0.80     |

## Jeu de données de référence (golden)

Constituer 50 à 100 triplets (question, réponse attendue, contexte source) à
partir des documents déjà ingérés :

1. Sélectionner 10 à 15 documents couvrant les types présents. Le corpus en
   service au 25 septembre 2026 ne compte que des chapitres HTML et un PDF
   (aucune note Markdown : `Datas/mds/` n'existe pas).
2. Écrire 5 à 7 questions par document, avec les réponses attendues.
3. Annoter les passages sources pertinents.
4. Versionner le jeu à côté du jeu de questions existant.

> **Attention aux identifiants.** Les ids de chunk dérivent du texte extrait et
> du chemin du document : toute évolution de la chaîne d'extraction, ou tout
> renommage d'un fichier du corpus, les change. Un jeu annoté par ids devient
> caduc à la première modification. Préférer annoter par `source_path` et
> extrait de texte attendu, et ne résoudre les ids qu'au moment de
> l'évaluation.

> **Point de comparaison.** `context_precision` est la métrique la plus
> sensible au nettoyage de l'index : avant le regroupement des fragments, 36 %
> des chunks récupérables étaient des fragments de mise en page (`x`, `and`,
> `-`). Une mesure antérieure à ce changement n'est pas comparable aux suivantes.

## Pipeline d'évaluation

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    context_precision,
    context_recall,
    answer_relevancy,
)

result = evaluate(
    dataset=golden_dataset,
    metrics=[faithfulness, context_precision, context_recall, answer_relevancy],
)
```

## Intégration continue

- Exécuter l'évaluation après chaque changement du retrieval ou des prompts.
- Comparer les scores avec la référence précédente.
- Alerter si une métrique passe sous le seuil.

## Métriques complémentaires (hors Ragas)

- **Latence P95** du retrieval (requête ChromaDB et reranking).
- **Tokens consommés** par requête (coût LLM).
- **Taux d'hallucination** (réponses non étayées par le contexte).
