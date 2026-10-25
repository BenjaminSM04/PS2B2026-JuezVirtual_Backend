# Experimento técnico sintético de defensa

Por autorización del responsable, esta entrega incorpora un experimento real sobre
datos sintéticos sin convertirlo en aprobación pedagógica. Los 144 ejemplos siguen
en estado `draft`, sin revisor ni fecha de aprobación. No hay entregas de estudiantes.

`ejemplos-sinteticos.json` contiene seis problemas, seis lenguajes y cuatro familias
de error. `observaciones-juez.json` conserva 144 veredictos y 36 controles correctos
Accepted observados en el juez del sistema, fijado por digest. El generador está en
`scripts/generate_defense_dataset.py` del repositorio de integración.

La partición por problema, semilla 2026, es 96/24/24 sin duplicados ni contaminación.
Las categorías representadas son compilation/runtime/logic/complexity. Concept y
unknown no tienen soporte. El veredicto separa fuertemente estas cuatro familias;
la exactitud sintética no acredita diagnóstico causal fino ni eficacia educativa.

El modo `--technical-demo` es explícito en construcción, carga, entrenamiento y
evaluación. Rechaza historia real y registros rechazados. El modo normal conserva
su requisito de revisión. El motor acepta un manifiesto técnico solo al activar
`TUTOR_TECHNICAL_DEMO=1` junto a `OJ_VERIFICATION_ONLY=1`; las salidas se identifican
como demostración, y la configuración normal lo rechaza.

La explicación de un concepto se obtiene siempre de la versión docente fijada,
incluso con el generador activo. No se sustituye por inferencia. Las pistas y
explicaciones de intentos pueden usar el modelo y mantienen su fuente/incertidumbre.

Se ajustó realmente Qwen2.5-Coder-1.5B-Instruct con QLoRA NF4, LoRA r=8/alpha=16,
fp16, tres épocas y semilla 2026. El entrenamiento tardó 500,49 s en RTX 2060 SUPER;
pérdida train 0,15985 y validación 0,01500. Estas pérdidas miden ajuste a objetivos
textuales sintéticos, no calidad pedagógica. Se compartió el formato de conversación
con el motor y se enmascararon los tokens del prompt en la pérdida.

La selección distingue el repositorio GGUF medido y la revisión safetensors
entrenable. Se fijaron archivos por checksum, revisión base
`2e1fd397ee46e1388853d2af2c993145b0f1098a` y llama.cpp
`c7fc5094179bf8a9c73c18593db714f8da41a402`. Fuente/licencia del modelo:
[ficha oficial](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct).

Los pesos/adaptadores/checkpoints permanecen fuera de Git. La conversión produce
GGUF Q4_K_M y un manifiesto con los hashes del generador, clasificador, dataset y
resultado de entrenamiento. Dependencias de conversión en
`deploy/requirements-export.txt`, separadas del backend.

Los resultados de comparación base/ajustado y la prueba navegador→juez→tutor se
publican sanitizados en `docs/defensa/` del deploy. El piloto se conserva como
propuesta no ejecutada y queda fuera del cierre funcional solicitado.
