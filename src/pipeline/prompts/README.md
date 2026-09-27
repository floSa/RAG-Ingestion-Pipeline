# Convention des prompts

Ce dossier est réservé aux modèles de prompts d'un agent RAG. Il ne contient
aucun modèle : la couche agent vit dans le projet `rag-agent-chat`, et ce
pipeline n'appelle aucun LLM. Aucun module de `src/` ne lit ce dossier.

## Règles

- Un fichier par prompt : `{nom_du_prompt}.txt` ou `.j2` (Jinja2).
- Aucun prompt en ligne dans le code Python.
- Variables entre accolades : `{context}`, `{question}`, `{history}`.
- Documenter les variables attendues en commentaire en tête de fichier.

## Structure envisagée

```
prompts/
    system.txt              # Prompt systeme de l'agent
    answer_with_context.j2  # Generation de reponse avec contexte
    summarize.j2            # Resume de document
    extract_entities.j2     # Extraction d'entites pour le graphe
```
