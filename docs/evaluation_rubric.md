# Rúbrica de Evaluación — LaborIA Colombia
**US-013 | Task-013-07 | eval_version: 1.0**

---

## Criterios y ponderación

| Criterio | Peso | Pregunta que responde |
|---|---|---|
| **Corrección técnica** | 40% | ¿Los conceptos son técnicamente correctos? ¿Hay errores factuales? |
| **Completitud** | 30% | ¿La respuesta cubre los `expected_topics` de la pregunta? |
| **Claridad** | 20% | ¿La explicación es clara, ordenada y fácil de seguir? |
| **Ejemplos** | 10% | ¿Incluye ejemplos, código o evidencia concreta? |

**Fórmula del score final:**
```
score = round(correctness*0.40 + completeness*0.30 + clarity*0.20 + examples*0.10)
```

---

## Niveles de score

Aplican igual al score final y a cada criterio individualmente.

| Rango | Nivel | Descripción |
|---|---|---|
| 85–100 | **Excelente** | Cubre el criterio sin gaps relevantes. Respuesta sólida que un profesional daría. |
| 70–84 | **Bueno** | Correcto en lo esencial. Solo gaps menores o detalles faltantes. |
| 50–69 | **Parcial** | Base correcta pero incompleto, o con errores no críticos. Feedback: "Correcto pero incompleto". |
| 0–49 | **Insuficiente** | Mayormente incorrecto, vacío, o no responde la pregunta. Feedback: "Incorrecto". |

---

## Reglas de feedback por score

Estas reglas las aplica el LLM en el Step 3 de su prompt:

- **score ≥ 85** → `strengths` con al menos 1 ítem específico. `correction` = null.
- **50 ≤ score < 70** → `improvements[0]` empieza con `"Correcto pero incompleto:"` + explicación de qué temas faltaron.
- **score < 30** → `improvements[0]` empieza con `"Incorrecto:"` + explicación del error conceptual específico.
- El feedback se escribe **en el mismo idioma que la respuesta del candidato**.

---

## Ejemplos de evaluación por nivel

### Excelente (score: 92)

**Pregunta:** ¿Qué es un decorador en Python?

**Respuesta del usuario:**
> Un decorador es una función que recibe otra función como argumento y extiende su comportamiento sin modificarla. Se usa con la sintaxis `@nombre`. Por ejemplo, `@login_required` verifica autenticación antes de ejecutar una vista. Son útiles para logging, control de acceso y caché.

**Evaluación:**
```json
{
  "score": 92,
  "score_breakdown": {
    "correctness": 95,
    "completeness": 95,
    "clarity": 90,
    "examples": 80
  },
  "feedback": {
    "strengths": ["Definición precisa", "Cubre todos los expected topics", "Ejemplo práctico y relevante"],
    "improvements": ["Podría mencionar los decoradores con argumentos para mayor completitud"],
    "correction": null
  },
  "topics_covered": ["función que envuelve otra función", "sintaxis @", "no modifica la función original"],
  "topics_missing": []
}
```

---

### Parcial (score: 58)

**Pregunta:** Explica los principales métodos HTTP usados en REST APIs.

**Respuesta del usuario:**
> Los métodos HTTP son GET para obtener datos y POST para crear recursos.

**Evaluación:**
```json
{
  "score": 58,
  "score_breakdown": {
    "correctness": 90,
    "completeness": 30,
    "clarity": 75,
    "examples": 40
  },
  "feedback": {
    "strengths": ["GET y POST descritos correctamente"],
    "improvements": ["Correcto pero incompleto: faltó mencionar PUT (actualizar), DELETE (eliminar), PATCH (actualizar parcialmente) e idempotencia"],
    "correction": null
  },
  "topics_covered": ["GET", "POST"],
  "topics_missing": ["PUT", "DELETE", "PATCH", "idempotencia"]
}
```

---

### Incorrecto (score: 15)

**Pregunta:** ¿Cuál es la complejidad temporal de buscar en un árbol binario de búsqueda balanceado?

**Respuesta del usuario:**
> La búsqueda en un BST es O(1) porque accedes al nodo directamente.

**Evaluación:**
```json
{
  "score": 15,
  "score_breakdown": {
    "correctness": 0,
    "completeness": 20,
    "clarity": 50,
    "examples": 0
  },
  "feedback": {
    "strengths": [],
    "improvements": ["Incorrecto: la complejidad de búsqueda en un BST balanceado es O(log n), no O(1). En cada nivel se descarta la mitad del árbol, resultando en tiempo logarítmico. O(1) aplica a estructuras como hash tables."],
    "correction": "La complejidad es O(log n) en un BST balanceado, O(n) en el peor caso (árbol degenerado)."
  },
  "topics_covered": [],
  "topics_missing": ["O(log n)", "tiempo logarítmico", "árbol balanceado"]
}
```

---

## Historial de versiones

| Versión | Fecha | Cambio |
|---|---|---|
| 1.0 | 2026-03 | Versión inicial. 4 criterios ponderados. Prompts con pasos numerados. |

---

## Notas para calibración

Si los tests de integración (`pytest -m integration`) fallan consistentemente fuera del rango esperado, revisar los logs de warning de `_log_score_discrepancy`. Los warnings indican cuánto difiere el score del modelo del score recalculado con la fórmula — diferencias > 15 puntos sugieren que el modelo no está aplicando la fórmula correctamente y el prompt de STEP 2 necesita refuerzo.
