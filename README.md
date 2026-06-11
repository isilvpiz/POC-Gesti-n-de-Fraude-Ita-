# POC Gestión de Fraude Itaú — Desarrollo Local en Kiro

## Descripción

Proyecto de desarrollo local para validar el flujo de dos agentes de IA orientados a la gestión automatizada de reclamos de fraude bancario. Este repositorio está preparado para ser abierto directamente en **Kiro** (IDE agentic de AWS).

---

## Arquitectura local (sin AWS)

```
input/emails/        → Correos .eml con PDF adjunto (simulan casilla email Itaú)
input/pdfs/          → PDFs de formularios de reclamo (adjuntos de los correos)
       ↓
agente1/             → Lee correo, extrae PDF, procesa con Bedrock → escribe Excel
output/casos.xlsx    → Output Agente 1 (simula escritura al Front de Fraudes)
       ↓
agente2/             → Lee output Agente 1, evalúa regla 3DS → escribe decisión
output/decisiones.xlsx → Output Agente 2 (simula decisión de chargeback)
```

---

## Agentes

### Agente 1 — Procesamiento de Correos de Fraude
- **Input:** archivos `.eml` en `input/emails/`
- **Proceso:** extrae PDF adjunto → lee contenido con Amazon Bedrock (Claude Haiku) → estructura datos del reclamo
- **Output:** `output/casos.xlsx` — un registro por correo procesado

### Agente 2 — Decisión de Chargeback 3DS
- **Input:** `output/casos.xlsx` generado por Agente 1
- **Proceso:** evalúa si el comercio tiene autenticación 3DS activa en el proceso de pago
- **Regla:** si el comercio **tiene 3DS** → no aplica chargeback / si **no tiene 3DS** → aplica chargeback
- **Output:** `output/decisiones.xlsx` — decisión y justificación por caso

---

## Flujo encadenado

```
Correo .eml + PDF adjunto
        ↓
    [Agente 1]
    Extrae datos del reclamo con Bedrock
        ↓
    output/casos.xlsx
    (RUT cliente, monto, comercio, fecha, tipo transacción, flag 3DS)
        ↓
    [Agente 2]
    Evalúa regla 3DS sobre datos extraídos
        ↓
    output/decisiones.xlsx
    (ID caso, decisión, justificación, fecha procesamiento)
```

---

## Estructura del repositorio

```
poc_itau/
├── README.md                    # Este archivo
├── .kiro/
│   ├── steering/
│   │   ├── general.md           # Reglas generales para Kiro
│   │   ├── agente1.md           # Reglas específicas Agente 1
│   │   └── agente2.md           # Reglas específicas Agente 2
│   └── specs/
│       ├── requirements.md      # Especificación funcional completa
│       ├── design.md            # Diseño técnico
│       └── tasks.md             # Plan de implementación
├── agente1/
│   ├── main.py                  # Entry point Agente 1
│   ├── email_reader.py          # Lectura y parseo de .eml
│   ├── pdf_extractor.py         # Extracción de texto desde PDF
│   ├── bedrock_client.py        # Cliente Amazon Bedrock (Claude Haiku)
│   └── excel_writer.py          # Escritura de resultados en Excel
├── agente2/
│   ├── main.py                  # Entry point Agente 2
│   ├── caso_reader.py           # Lectura del output de Agente 1
│   ├── regla_3ds.py             # Lógica de evaluación regla 3DS
│   └── decision_writer.py       # Escritura de decisión en Excel
├── input/
│   ├── emails/                  # Correos .eml de prueba
│   └── pdfs/                    # PDFs de formularios de reclamo
├── output/
│   ├── casos.xlsx               # Output Agente 1
│   └── decisiones.xlsx          # Output Agente 2
├── tests/
│   ├── test_agente1.py          # Tests unitarios Agente 1
│   └── test_agente2.py          # Tests unitarios Agente 2
├── docs/
│   └── manual_operacion.md      # Manual de operación y pruebas
├── requirements.txt             # Dependencias Python
└── .env.example                 # Variables de entorno requeridas
```

---

## Requisitos previos

- Python 3.11+
- Cuenta AWS con acceso a Amazon Bedrock (Claude Haiku) habilitado
- Kiro instalado ([kiro.dev](https://kiro.dev))
- Credenciales AWS configuradas (`aws configure`)

## Instalación

```bash
git clone <repo>
cd poc_itau
pip install -r requirements.txt
cp .env.example .env
# Editar .env con tus credenciales AWS
```

## Ejecución

```bash
# Ejecutar Agente 1 (procesa correos en input/emails/)
python agente1/main.py

# Ejecutar Agente 2 (procesa output de Agente 1)
python agente2/main.py

# Ejecutar flujo completo
python agente1/main.py && python agente2/main.py
```

---

## Variables de entorno

```
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-haiku-3-5
INPUT_EMAIL_DIR=input/emails
INPUT_PDF_DIR=input/pdfs
OUTPUT_DIR=output
LOG_LEVEL=INFO
```
