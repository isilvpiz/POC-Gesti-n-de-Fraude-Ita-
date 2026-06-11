# Tasks — Agente 1

- [ ] T1. Setup: requirements.txt, .env.example (con AWS_PROFILE), config.py con validación de variables
- [ ] T2. `email_reader.py` — LectorCorreo + test con caso_001.eml
- [ ] T3. `pdf_extractor.py` — ExtractorPDF + test con formulario_001.pdf
- [ ] T4. `pii.py` — enmascaramiento RUT + filtro de logger + tests
- [ ] T5. `bedrock_client.py` — Converse API, retries nativos boto3, extracción 13 campos JSON + test con mock
- [ ] T6. `dedup.py` — hash sha256(rut+operacion+monto) + verificación contra Excel + test
- [ ] T7. `excel_writer.py` — EscritorCasos con todas las columnas + test
- [ ] T8. `main.py` — orquestación completa + log resumen (procesados/errores/pendientes/duplicados)
- [ ] T9. Test integración: 3 .eml de input/emails/ → verificar casos.xlsx con estados esperados
